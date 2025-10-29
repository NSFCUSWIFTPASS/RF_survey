import asyncio
import time
from typing import Protocol, Optional
from enum import Enum, auto
from dataclasses import dataclass

from rf_shared.interfaces import ILogger


class IHeartbeatManager(Protocol):
    async def run(self) -> None:
        """The main execution loop for the heartbeat manager."""
        ...

    async def notify_sample_success(self) -> None:
        """Notify the manager that a sample was successfully processed."""


@dataclass
class HeartbeatConfig:
    guid: str
    timeout_seconds: float


class TaskEvent(Enum):
    NOTIFY_SAMPLE_SUCCESS = auto()


class HeartbeatManager:
    def __init__(
        self,
        config: HeartbeatConfig,
        shutdown_event: asyncio.Event,
        logger: ILogger,
    ):
        self.config = config
        self.shutdown_event = shutdown_event
        self._event_queue = asyncio.Queue()
        self.logger = logger

    @classmethod
    def create(
        cls,
        heartbeat_guid: Optional[str],
        sample_interval: int,
        shutdown_event: asyncio.Event,
        logger: ILogger,
    ) -> IHeartbeatManager:
        """
        Factory method that creates a manager.

        Returns:
            A tuple of (IHeartbeatManager instance, event_queue instance).
        """
        if heartbeat_guid:
            timeout_seconds = sample_interval + 10  # add some buffer time

            heartbeat_config = HeartbeatConfig(
                guid=heartbeat_guid, timeout_seconds=timeout_seconds
            )

            return HeartbeatManager(
                config=heartbeat_config,
                shutdown_event=shutdown_event,
                logger=logger,
            )
        else:
            return NullHeartbeatManager(shutdown_event=shutdown_event)

    async def run(self):
        """
        Handles heartbeats and acts as a watchdog for the survey task.
        """
        self.logger.info(
            f"Heartbeat/Watchdog task started. Survey timeout is {self.config.timeout_seconds} seconds.",
        )
        last_pet_time = time.monotonic()

        while not self.shutdown_event.is_set():
            try:
                message = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)

                if message == TaskEvent.NOTIFY_SAMPLE_SUCCESS:
                    last_pet_time = time.monotonic()

                # Mark the message as processed
                self._event_queue.task_done()

            except asyncio.TimeoutError:
                # Send heartbeat API call
                self.logger.info(f"tick... sending heartbeat for: {self.config.guid}")

                # Check watchdog
                if time.monotonic() - last_pet_time > self.config.timeout_seconds:
                    self.logger.critical("WATCHDOG: Survey task appears hung!")
                    self.shutdown_event.set()
                    break

            except Exception as e:
                self.logger.error(f"Heartbeat failed: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def notify_sample_success(self):
        await self._event_queue.put(TaskEvent.NOTIFY_SAMPLE_SUCCESS)


class NullHeartbeatManager:
    def __init__(
        self,
        shutdown_event: asyncio.Event,
    ):
        """
        A do-nothing HeartbeatManager that satisfies the interface.
        Used for when the rf-survey application is ran without heartbeats.
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

    async def notify_sample_success(self):
        pass
