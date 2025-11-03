import asyncio
import signal
from typing import Any, Dict, Optional
from pydantic import ValidationError
from copy import deepcopy

from rf_shared.nats_client import NatsProducer
from rf_shared.interfaces import ILogger
from rf_shared.checksum import get_checksum
from rf_shared.models import MetadataRecord
from zmsclient.zmc.v1.models import MonitorStatus

from rf_survey.models import ReceiverConfig, SweepConfig, ApplicationInfo, ProcessingJob
from rf_survey.monitor import IZmsMonitor
from rf_survey.receiver import Receiver
from rf_survey.validators import ZmsReconfigurationParams
from rf_survey.watchdog import ApplicationWatchdog


class SurveyApp:
    """
    Encapsulates the state and logic for the RF Survey application.
    """

    def __init__(
        self,
        app_info: ApplicationInfo,
        sweep_config: SweepConfig,
        shutdown_event: asyncio.Event,
        receiver: Receiver,
        producer: NatsProducer,
        watchdog: ApplicationWatchdog,
        zms_monitor: IZmsMonitor,
        logger: ILogger,
    ):
        self.logger = logger
        self.shutdown_event = shutdown_event

        self.app_info = app_info

        self.sweep_config = sweep_config
        self.receiver = receiver
        self.producer = producer
        self.watchdog = watchdog

        self.zms_monitor = zms_monitor
        self._running_event = asyncio.Event()
        self._active_sweep_task: Optional[asyncio.Task] = None

    def _signal_handler(self):
        """Sets the shutdown event when a signal is received."""
        if not self.shutdown_event.is_set():
            self.logger.info("Shutdown signal received. Signalling tasks to stop.")
            self.shutdown_event.set()

    async def start_survey(self):
        """Signals the survey runner to start and resumes the watchdog."""
        self.logger.info("Survey is being started/resumed.")
        await self.watchdog.resume()
        self._running_event.set()

    async def pause_survey(self):
        """Signals the survey runner to pause and pauses the watchdog."""
        self.logger.warning("Survey is being paused.")
        await self.watchdog.pause()
        self._running_event.clear()

    async def run(self):
        """
        Initializes resources, runs the main application loop, and cleans up.
        """
        loop = asyncio.get_running_loop()
        survey_task = None
        monitor_task = None
        shutdown_waiter_task = None
        all_tasks = []

        try:
            self.receiver.initialize()
            # Store for metadata creation
            self.serial = self.receiver.serial
            await self.producer.connect()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._signal_handler)

            survey_task = asyncio.create_task(self._survey_runner())
            monitor_task = asyncio.create_task(self.zms_monitor.run())
            watchdog_task = asyncio.create_task(self.watchdog.run())
            shutdown_waiter_task = asyncio.create_task(self.shutdown_event.wait())

            all_tasks.extend(
                [survey_task, monitor_task, watchdog_task, shutdown_waiter_task]
            )

            await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)

        except Exception as e:
            self.logger.error(f"Critical error in run loop: {e}", exc_info=True)
            self.shutdown_event.set()

        finally:
            self.logger.info("Cleaning up resources...")

            for task in all_tasks:
                if task and not task.done():
                    task.cancel()

            created_tasks = [t for t in all_tasks if t is not None]
            if created_tasks:
                await asyncio.gather(*created_tasks, return_exceptions=True)

            await self.producer.close()
            self.logger.info("Shutdown complete.")

    async def _survey_runner(self):
        """
        A supervisor loop that manages the lifecycle of the sweep task.

        It waits for the application to be in a "running" state, then starts
        a sweep as a cancellable sub-task. If a pause or reconfiguration
        command is received, the `apply_zms_reconfiguration` method will cancel
        the active sweep task, and this loop will gracefully handle the
        cancellation and then re-evaluate the application's state (e.g.,
        it will pause if the running event has been cleared).
        """
        self.logger.info("Survey runner supervisor started.")

        cycles_run = 0

        try:
            while not self.shutdown_event.is_set():
                # Check if we've completed our cycles if configured
                target_cycles = self.sweep_config.cycles
                if target_cycles > 0 and cycles_run >= target_cycles:
                    self.logger.info(
                        f"Completed {target_cycles} configured sweep cycles. Survey runner is finished."
                    )
                    break

                # This is the primary pausing mechanism. It will block here
                # indefinitely if the application is paused.
                await self._running_event.wait()

                # Check if a shutdown was signaled
                if self.shutdown_event.is_set():
                    break

                # In a running state. Create the sweep as a new task
                # and store a reference to it so it can be cancelled externally.
                self.logger.info("Starting a new sweep task.")
                self._active_sweep_task = asyncio.create_task(
                    self._perform_sweep(self.sweep_config)
                )

                try:
                    # This will wait until the sweep finishes its full run,
                    # OR it will raise a CancelledError if an external
                    # command (like a pause) cancels it.
                    await self._active_sweep_task
                    cycles_run += 1

                    self.logger.info("Sweep task completed successfully.")

                except asyncio.CancelledError:
                    self.logger.info("Sweep task was cancelled by an external command.")

                finally:
                    self._active_sweep_task = None

        except asyncio.CancelledError:
            self.logger.info("Survey runner supervisor was cancelled.")

        except Exception as e:
            self.logger.critical(
                f"A critical error occurred in the survey runner supervisor: {e}",
                exc_info=True,
            )

        finally:
            if self._active_sweep_task and not self._active_sweep_task.done():
                self._active_sweep_task.cancel()

            self.logger.info("Survey runner supervisor has shut down.")

    async def _perform_sweep(self, sweep_config: SweepConfig):
        """
        Performs a single sweep across the specified frequency range.
        """
        center_hz = sweep_config.start_hz
        end_hz = sweep_config.end_hz
        step_hz = self.receiver.config.bandwidth_hz

        while center_hz <= end_hz and not self.shutdown_event.is_set():
            try:
                for _ in range(sweep_config.records_per_step):
                    wait_duration = sweep_config.next_collection_wait_duration()

                    await self._wait_until_next_collection(wait_duration)

                    # If we were shut down while waiting check again before proceeding
                    if self.shutdown_event.is_set():
                        break

                    receiver_config_snapshot = deepcopy(self.receiver.config)
                    sweep_config_snapshot = deepcopy(sweep_config)

                    raw_capture = await self.receiver.receive_samples(center_hz)

                    if raw_capture is None:
                        continue

                    job = ProcessingJob(
                        raw_capture=raw_capture,
                        receiver_config_snapshot=receiver_config_snapshot,
                        sweep_config_snapshot=sweep_config_snapshot,
                    )

                    metadata_record = await self._process_capture_job(job)
                    await self.producer.publish_metadata(metadata_record)

                    await self.watchdog.pet()

            except asyncio.CancelledError:
                raise

            except Exception as e:
                # This is a transient error for a single frequency step.
                self.logger.error(f"Failed to perform capture at {center_hz} Hz: {e}")
                self.logger.warning(
                    "Skipping this frequency step and continuing sweep."
                )

            center_hz += step_hz

    async def _process_capture_job(self, job: ProcessingJob) -> MetadataRecord:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_capture_job_blocking, job)

    def _process_capture_job_blocking(self, job: ProcessingJob) -> MetadataRecord:
        """
        This function takes a complete ProcessingJob,
        performs blocking I/O (saving the file), checksumming
        and returns a final MetadataRecord.
        """

        raw_capture = job.raw_capture
        receiver_config = job.receiver_config_snapshot
        sweep_config = job.sweep_config_snapshot

        timestamp_str = raw_capture.capture_timestamp.strftime("D%Y%m%dT%H%M%SM%f")

        filename = f"{self.serial}-{self.app_info.hostname}-{timestamp_str}.sc16"
        file_path = self.app_info.output_path / filename

        try:
            with open(file_path, "wb") as f:
                f.write(raw_capture.iq_data_bytes)
            self.logger.info(f"File stored as {file_path}")
        except IOError as e:
            self.logger.error(
                f"Failed to write capture file to disk: {e}", exc_info=True
            )
            raise

        file_checksum = get_checksum(raw_capture.iq_data_bytes)
        self.logger.info(f"Calculated checksum: {file_checksum}")

        metadata_record = MetadataRecord(
            # Static application info
            hostname=self.app_info.hostname,
            organization=self.app_info.organization,
            gcs=self.app_info.coordinates,
            group=self.app_info.group,
            # this is pulled after initial initalize
            serial=self.serial,
            bit_depth=16,
            # Configuration context from the snapshots
            interval=sweep_config.interval_sec,
            length=receiver_config.duration_sec,
            gain=receiver_config.gain_db,
            sampling_rate=receiver_config.bandwidth_hz,
            # Direct data from the capture itself
            frequency=raw_capture.center_freq_hz,
            timestamp=raw_capture.capture_timestamp,
            # Data generated during this processing step
            source_path=file_path,
            checksum=file_checksum,
        )

        return metadata_record

    async def _wait_until_next_collection(self, wait_duration: float) -> None:
        try:
            self.logger.info(
                f"Waiting for {wait_duration:.4f} seconds before next collection..."
            )
            await asyncio.wait_for(self.shutdown_event.wait(), timeout=wait_duration)

        except asyncio.TimeoutError:
            # This is the normal, the timer finished
            pass

    async def _cancel_sweep_task(self):
        if self._active_sweep_task and not self._active_sweep_task.done():
            self.logger.warning(
                "Reconfiguration received during an active sweep. Cancelling the sweep."
            )
            self._active_sweep_task.cancel()
            try:
                await asyncio.wait_for(self._active_sweep_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    async def apply_zms_reconfiguration(
        self, status: MonitorStatus, params: Optional[Dict[str, Any]]
    ) -> None:
        """
        Validates the raw ZMS parameters, then dispatches the configs
        to the sub-components. This is a callback pased to ZMS Monitor task.
        Raises ValueError on validation failure.
        """
        self.logger.info(f"Validating and applying ZMS reconfiguration: {params}")

        if status == MonitorStatus.PAUSED:
            await self.pause_survey()
        else:
            await self.start_survey()

        # Cancel current sweep task as it is no longer valid after a reconfig
        await self._cancel_sweep_task()

        # No params were specified for update
        if not params:
            return

        try:
            validated_params = ZmsReconfigurationParams(**params)

        except ValidationError as e:
            error_details = e.errors()
            self.logger.error(f"ZMS parameter validation failed: {error_details}")
            raise ValueError(f"Invalid parameters from ZMS: {error_details}") from e

        new_receiver_config = ReceiverConfig(
            gain_db=validated_params.gain_db,
            duration_sec=validated_params.duration_sec,
            bandwidth_hz=validated_params.bandwidth_hz,
        )

        new_sweep_config = SweepConfig(
            start_hz=validated_params.start_freq_hz,
            end_hz=validated_params.end_freq_hz,
            interval_sec=validated_params.sample_interval,
            # Carry over values that are not set by ZMS
            cycles=self.sweep_config.cycles,
            records_per_step=self.sweep_config.records_per_step,
            max_jitter_sec=self.sweep_config.max_jitter_sec,
        )

        if new_receiver_config != self.receiver.config:
            await self.receiver.reconfigure(new_receiver_config)

        if new_sweep_config != self.sweep_config:
            self.sweep_config = new_sweep_config
