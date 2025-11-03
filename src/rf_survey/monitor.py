import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Protocol, Optional
from websockets.asyncio.client import ClientConnection

from rf_shared.interfaces import ILogger

from zmsclient.zmc.client_asyncio import ZmsZmcClientAsyncio
from zmsclient.zmc.v1.models import (
    Subscription,
    EventFilter,
    MonitorState,
    MonitorStatus,
    MonitorOpStatus,
    MonitorPending,
    UpdateMonitorStateOpStatus,
    Error,
    Event,
    AnyObject,
)

from rf_survey.commands import (
    MonitorCommand,
    ProcessReconfigurationCommand,
)
from rf_survey.zms_event_subscriber import ZmsEventSubscriber
from rf_survey.types import ReconfigurationCallback

EVENT_SOURCETYPE_ZMC = 2
EVENT_CODE_MONITOR = 2005
EVENT_CODE_MONITOR_STATE = 2009
EVENT_CODE_MONITOR_PENDING = 2010
EVENT_CODE_MONITOR_ACTION = 2011
EVENT_CODE_MONITOR_TASK = 2012

MONITOR_EVENT_CODES = {
    EVENT_CODE_MONITOR_PENDING,
}


class IZmsMonitor(Protocol):
    async def run(self) -> None:
        """The main execution loop for the Zms monitor."""
        ...


class ZmsMonitor:
    def __init__(
        self,
        monitor_id: str,
        element_id: str,
        user_id: str,
        zmc_client: ZmsZmcClientAsyncio,
        reconfiguration_callback: ReconfigurationCallback,
        shutdown_event: asyncio.Event,
        logger: ILogger,
    ):
        self.shutdown_event = shutdown_event
        self._status_queue = asyncio.Queue()
        self._command_queue = asyncio.Queue()
        self.logger = logger
        self.zmc_client = zmc_client
        self.reconfiguration_callback = reconfiguration_callback

        self.monitor_id = monitor_id
        self.user_id = user_id
        self.element_id = element_id

        # State managed by the loop
        self._op_status: MonitorOpStatus = MonitorOpStatus.ACTIVE
        self._current_parameters: Optional[AnyObject] = None
        self._status_ack_by: Optional[datetime] = None
        self._last_pending_id_to_ack: Optional[str] = None
        self._last_pending_outcome: Optional[int] = None
        self._last_pending_message: Optional[str] = None

    async def run(self):
        self.logger.info("ZmsMonitor task starting...")
        tasks = []
        try:
            # Check Zms for our monitor state and send initial heartbeat
            if not await self._initialize_state():
                self.logger.error("Failed to initialize monitor state. Shutting down.")
                self.shutdown_event.set()
                return

            event_listener_task = asyncio.create_task(self._event_listener_loop())
            state_machine_task = asyncio.create_task(self._state_machine_loop())
            tasks.extend([event_listener_task, state_machine_task])

            await asyncio.gather(*tasks)

        except asyncio.CancelledError:
            self.logger.info("ZmsMonitor task was cancelled.")

        except Exception as e:
            self.logger.critical(
                f"A critical error occurred in ZmsMonitor: {e}", exc_info=True
            )
            self.shutdown_event.set()

        finally:
            self.logger.info("ZmsMonitor cleaning up its sub-tasks...")
            for task in tasks:
                task.cancel()

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _initialize_state(self) -> bool:
        """
        Fetches the initial Monitor object from OpenZMS, determines the target
        config via (pending or state), applies that configuration, and
        sends the first heartbeat.
        """
        self.logger.info(f"Fetching initial state for monitor {self.monitor_id}...")
        try:
            response = await self.zmc_client.get_monitor(
                monitor_id=self.monitor_id, elaborate=True
            )
            monitor = response.parsed
            if isinstance(monitor, Error):
                self.logger.error(f"Failed to get monitor object: {monitor.error}")
                return False

            target_config = None
            pending_id_to_ack = None

            if monitor.pending and monitor.pending.id != monitor.state.last_pending_id:
                self.logger.info(
                    f"Found unacknowledged pending config (ID: {monitor.pending.id}). "
                    "Using it as the target config for initialization."
                )
                target_config = monitor.pending
                pending_id_to_ack = monitor.pending.id
            else:
                self.logger.info(
                    "Using current monitor state as the target config for initialization."
                )
                target_config = monitor.state

            # Determine target status and parameters
            target_status = target_config.status
            target_parameters = getattr(target_config, "parameters", None)
            params_dict = target_parameters.to_dict() if target_parameters else None

            self.logger.info(
                f"Applying initial configuration. Target status: '{target_status.value}'"
            )

            # Set operational status based on the target
            self._update_op_status_from_target(target_status)

            await self.reconfiguration_callback(target_status, params_dict)

            # Apply parameters from the target
            if target_parameters:
                self.logger.info(
                    f"Applied new parameters: {target_parameters.to_dict()}"
                )
                self._current_parameters = target_parameters

            # Setup the acks for the pending event
            if pending_id_to_ack:
                self._prepare_for_ack(
                    pending_id_to_ack, 0, "Configuration applied successfully."
                )

            self.logger.info(
                f"Sending initial heartbeat with op_status '{self._op_status.value}'."
            )
            await self._send_heartbeat()

            return True

        except Exception as e:
            self.logger.error(f"Failed during state initialization: {e}", exc_info=True)
            return False

    async def _state_machine_loop(self):
        """The main loop that waits for commands or heartbeat timeouts."""
        while not self.shutdown_event.is_set():
            try:
                time_until_ack_by: Optional[float] = None

                # Determine the deadline for the next heartbeat
                if self._status_ack_by:
                    now = datetime.now(timezone.utc)
                    if self._status_ack_by > now:
                        time_until_ack_by = (self._status_ack_by - now).total_seconds()
                    else:
                        self.logger.warning(
                            "Heartbeat deadline is in the past! Sending immediately."
                        )
                        time_until_ack_by = 0

                try:
                    command = await asyncio.wait_for(
                        self._command_queue.get(), timeout=time_until_ack_by
                    )
                    await self._process_command(command)

                except asyncio.TimeoutError:
                    self.logger.debug("Heartbeat interval expired. Sending heartbeat.")
                    await self._send_heartbeat()

            except asyncio.CancelledError:
                self.logger.info("State machine loop cancelled.")
                break
            except Exception as e:
                self.logger.error(
                    f"Error in state machine loop: {e}. Retrying in 10s.", exc_info=True
                )
                await asyncio.sleep(10)

    async def _event_listener_loop(self):
        self.logger.info("Starting WebSocket listener...")

        try:
            filter = EventFilter(element_ids=[self.element_id], user_ids=[self.user_id])
            subscription_config = Subscription(id=str(uuid.uuid4()), filters=[filter])

            adapter = ZmsEventAdapter(
                self.zmc_client,
                self._command_queue,
                self.monitor_id,
                subscription=subscription_config,
                reconnect_on_error=True,
            )

            await adapter.run_async()

        except asyncio.CancelledError:
            self.logger.info("WebSocket listener task cancelled.")
        except Exception as e:
            self.logger.critical(
                f"WebSocket listener failed critically: {e}", exc_info=True
            )
            self.shutdown_event.set()

    async def _process_command(self, command: MonitorCommand):
        self.logger.debug(f"Received COMMAND: {command}")

        match command:
            case ProcessReconfigurationCommand(pending=pending_config):
                target_status = getattr(pending_config, "status", None)
                if not target_status:
                    self.logger.error(
                        f"Received invalid MonitorPending object with no status. Ignoring: {pending_config}"
                    )
                    return

                pending_id = getattr(pending_config, "id", None)
                if not pending_id:
                    self.logger.error(
                        f"Received invalid MonitorPending object with no id. Ignoring: {pending_config}"
                    )
                    return

                target_parameters = getattr(pending_config, "parameters", None)
                params_dict = target_parameters.to_dict() if target_parameters else None

                self._update_op_status_from_target(target_status)

                self.logger.info(
                    f"Processing reconfiguration for MonitorPending ID {pending_id}. "
                    f"New target status: {target_status}"
                )

                try:
                    # If we get here, the configuration was successful.
                    await self.reconfiguration_callback(target_status, params_dict)

                    if target_parameters:
                        self.logger.info(
                            f"Applied new parameters: {target_parameters.to_dict()}"
                        )
                        self._current_parameters = target_parameters

                    self._prepare_for_ack(
                        pending_id, 0, "Configuration applied successfully"
                    )

                except Exception as e:
                    # The configuration logic failed.
                    self.logger.error(
                        f"Failed to apply new configuration: {e}", exc_info=True
                    )
                    self._prepare_for_ack(
                        pending_id, 1, f"Failed to apply configuration: {e}"
                    )

                await self._send_heartbeat()

            case _:
                self.logger.warning(
                    f"Received an unhandled command type: {type(command)}"
                )

    async def _send_heartbeat(self):
        """Constructs and sends a heartbeat PUT request to the ZMS API."""
        body = UpdateMonitorStateOpStatus(
            op_status=self._op_status, parameters=self._current_parameters
        )

        if self._last_pending_id_to_ack:
            body.last_pending_id = self._last_pending_id_to_ack
            body.last_pending_outcome = self._last_pending_outcome
            body.last_pending_message = self._last_pending_message

        try:
            self.logger.debug(f"Sending heartbeat: {body.to_dict()}")
            response = await self.zmc_client.update_monitor_state_op_status(
                monitor_id=self.monitor_id, body=body
            )
            state = response.parsed
            if isinstance(state, MonitorState):
                # Successfully sent, update the next deadline
                if state.status_ack_by:
                    self._status_ack_by = state.status_ack_by
                    self.logger.debug(
                        f"Next heartbeat due by: {self._status_ack_by.isoformat()}"
                    )
                else:
                    self.logger.debug("No next heartbeat required by ZMS for now.")

                self._clear_ack_state()

            else:
                self.logger.error(
                    f"Heartbeat failed. Server response: {state.error if isinstance(state, Error) else 'Unknown'}"
                )

        except Exception as e:
            self.logger.error(
                f"Heartbeat Monitor PUT request failed: {e}", exc_info=True
            )

    def _update_op_status_from_target(self, target_status: MonitorStatus) -> None:
        if target_status == MonitorStatus.PAUSED:
            self._op_status = MonitorOpStatus.PAUSED
        else:
            # For any other target status (ACTIVE, DEGRADED, DOWN),
            # if the monitor is running, its operational status is ACTIVE.
            self._op_status = MonitorOpStatus.ACTIVE

    def _prepare_for_ack(self, pending_id: str, outcome: int, message: str) -> None:
        self._last_pending_id_to_ack = pending_id
        self._last_pending_outcome = outcome
        self._last_pending_message = message

    def _clear_ack_state(self) -> None:
        self._last_pending_id_to_ack = None
        self._last_pending_outcome = None
        self._last_pending_message = None

    async def pet_watchdog(self):
        await self._command_queue.put(PetWatchdogCommand())


class ZmsEventAdapter(ZmsEventSubscriber):
    def __init__(
        self,
        zmc_client: ZmsZmcClientAsyncio,
        command_queue: asyncio.Queue,
        monitor_id: str,
        **kwargs,
    ):
        super().__init__(zmsclient=zmc_client, **kwargs)
        self._command_queue = command_queue
        self.logger = logging.getLogger(__name__).getChild("ZmsEventAdapter")
        self.monitor_id = monitor_id

    async def on_event(self, ws: ClientConnection, evt: Event, message: bytes | str):
        if evt.header.source_type != EVENT_SOURCETYPE_ZMC:
            self.logger.error(
                "on_event: unexpected source type: %r (%r)",
                evt.header.source_type,
                message,
            )
            return

        if evt.header.code not in MONITOR_EVENT_CODES:
            return

        event_monitor_id = None

        if evt.header.code == EVENT_CODE_MONITOR:
            event_monitor_id = getattr(evt.object_, "id", None)
        else:
            event_monitor_id = getattr(evt.object_, "monitor_id", None)

        if event_monitor_id is None:
            self.logger.warning(
                f"Event with code {evt.header.code} "
                "was missing the required monitor ID attribute. Ignoring."
            )
            return

        if event_monitor_id != self.monitor_id:
            # An event for not our monitor
            return

        match evt.header.code:
            case EVENT_CODE_MONITOR_PENDING:
                if isinstance(evt.object_, MonitorPending):
                    pending_config = evt.object_
                    self.logger.info(
                        f"Received and queueing reconfiguration command for pending ID: {pending_config.id}"
                    )

                    await self._command_queue.put(
                        ProcessReconfigurationCommand(pending=pending_config)
                    )
                else:
                    self.logger.warning(
                        "Received a MONITOR_PENDING event but its payload was not a valid "
                        f"MonitorPending object. Type was: {type(evt.object_)}"
                    )


class NullZmsMonitor:
    def __init__(
        self,
        shutdown_event: asyncio.Event,
    ):
        """
        A do-nothing ZmsMonitor that satisfies the interface.
        Used for when the rf-survey application is ran in standalone.
        """
        self.shutdown_event = shutdown_event

    async def run(self) -> None:
        """
        The run method does nothing but wait for the application to shut down.
        """
        try:
            await self.shutdown_event.wait()
        except asyncio.CancelledError:
            pass
