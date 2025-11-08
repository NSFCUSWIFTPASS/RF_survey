import asyncio
from typing import Any, Dict, Optional
from pydantic import ValidationError
from copy import deepcopy

from rf_shared.nats_client import NatsProducer
from rf_shared.interfaces import ILogger
from rf_shared.checksum import get_checksum
from rf_shared.models import MetadataRecord, Envelope
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
        shutdown_event: asyncio.Event,
        app_info: ApplicationInfo,
        sweep_config: SweepConfig,
        receiver: Receiver,
        producer: NatsProducer,
        watchdog: ApplicationWatchdog,
        zms_monitor: IZmsMonitor,
        logger: ILogger,
    ):
        self.logger = logger
        self._shutdown_event = shutdown_event

        self.app_info = app_info

        self.sweep_config = sweep_config
        self.receiver = receiver
        self.producer = producer
        self.watchdog = watchdog

        self.zms_monitor = zms_monitor
        self._running_event = asyncio.Event()
        self._active_sweep_task: Optional[asyncio.Task] = None

        self._processing_queue = asyncio.Queue(maxsize=32)

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
        try:
            self.receiver.initialize()
            # Store for metadata creation
            self.serial = self.receiver.serial
            await self.producer.connect()

            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._survey_runner())
                tg.create_task(self._processing_worker())
                tg.create_task(self.zms_monitor.run())
                tg.create_task(self.watchdog.run())
                tg.create_task(self._queue_monitor())

        except asyncio.CancelledError:
            self.logger.info(
                "Main application task cancelled. Shutting down gracefully."
            )

        except Exception as e:
            self.logger.error(f"Critical error in run loop: {e}", exc_info=True)

        finally:
            self.logger.info("Cleaning up resources...")
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
            while True:
                target_cycles = self.sweep_config.cycles
                if target_cycles > 0 and cycles_run >= target_cycles:
                    self.logger.info(
                        f"Completed {target_cycles} configured cycles. Finishing."
                    )
                    break

                # Primary pausing mechanisim
                await self._running_event.wait()

                self.logger.debug("Starting a new sweep task.")
                receiver_config_snapshot = deepcopy(self.receiver.config)
                sweep_config_snapshot = deepcopy(self.sweep_config)

                self._active_sweep_task = asyncio.create_task(
                    self._perform_sweep(sweep_config_snapshot, receiver_config_snapshot)
                )

                try:
                    await self._active_sweep_task

                except asyncio.CancelledError:
                    if self._shutdown_event.is_set():
                        self.logger.info(
                            "Survey runner supervisor is being cancelled; propagating cancellation."
                        )
                        raise
                    else:
                        # If the supervisor isn't being cancelled, it must have been a
                        # cancel from a reconfigure.
                        self.logger.info(
                            "Active sweep was cancelled by a reconfigure command."
                        )

                else:
                    # This runs only if the sweep completed successfully.
                    cycles_run += 1
                    self.logger.debug("Sweep task completed successfully.")

                finally:
                    self._active_sweep_task = None

        except Exception as e:
            self.logger.critical(
                f"Critical error in survey runner supervisor: {e}", exc_info=True
            )

        finally:
            if self._active_sweep_task and not self._active_sweep_task.done():
                self._active_sweep_task.cancel()
            self.logger.info("Survey runner supervisor has shut down.")

    async def _perform_sweep(
        self, sweep_config: SweepConfig, receiver_config: ReceiverConfig
    ):
        """
        Performs a single sweep across the specified frequency range.
        """
        center_hz = sweep_config.start_hz
        end_hz = sweep_config.end_hz
        step_hz = receiver_config.bandwidth_hz

        while center_hz <= end_hz:
            try:
                for _ in range(sweep_config.records_per_step):
                    wait_duration = sweep_config.next_collection_wait_duration()

                    await self._wait_until_next_collection(wait_duration)

                    # Get the samples from receiver
                    raw_capture = await self.receiver.receive_samples(center_hz)

                    if raw_capture is None:
                        continue

                    # Create a processing job
                    job = ProcessingJob(
                        raw_capture=raw_capture,
                        receiver_config_snapshot=receiver_config,
                        sweep_config_snapshot=sweep_config,
                    )

                    await self.watchdog.pet()

                    try:
                        # Send job to processing task
                        await asyncio.wait_for(
                            self._processing_queue.put(job), timeout=1.0
                        )
                        self.logger.debug(
                            "Successfully queued capture job for processing."
                        )
                    except asyncio.TimeoutError:
                        self.logger.error(
                            "Processing queue is full! The system is backlogged. Dropping capture."
                        )
                        continue

            except Exception as e:
                # This is a transient error for a single frequency step
                self.logger.error(f"Failed to perform capture at {center_hz} Hz: {e}")
                self.logger.warning(
                    "Skipping this frequency step and continuing sweep."
                )

            center_hz += step_hz

    async def _processing_worker(self):
        """
        A consumer task that pulls capture jobs from a queue and
        processes them.
        """
        self.logger.info("Processing worker started.")

        try:
            while True:
                try:
                    # Get job from the queue
                    job = await asyncio.wait_for(
                        self._processing_queue.get(), timeout=1.0
                    )
                    # Process the job
                    await self._process_single_job(job)

                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            self.logger.info("Processing worker task cancelled.")

        finally:
            self.logger.info(
                f"Processing worker shutting down. Draining {self._processing_queue.qsize()} remaining jobs..."
            )
            # Drain the remaining jobs... Might be overkill
            while not self._processing_queue.empty():
                job = self._processing_queue.get_nowait()
                self.logger.info("Processing one final job before exit...")
                await self._process_single_job(job)

            self.logger.info("Processing queue is empty. Worker finished.")

    async def _process_single_job(self, job: ProcessingJob):
        """
        Helper function to process one job.
        """
        try:
            self.logger.debug(
                f"Processing job for capture at {job.raw_capture.center_freq_hz} Hz..."
            )

            metadata_record = await self._process_capture_job(job)
            await self.publish_metadata(metadata_record)

            self.logger.debug("Processing job finished successfully.")

        except Exception as e:
            self.logger.error(f"Failed to process capture job: {e}", exc_info=True)

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
            self.logger.debug(f"File stored as {file_path}")
        except IOError as e:
            self.logger.error(
                f"Failed to write capture file to disk: {e}", exc_info=True
            )
            raise

        file_checksum = get_checksum(raw_capture.iq_data_bytes)
        self.logger.debug(f"Calculated checksum: {file_checksum}")

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

    async def publish_metadata(self, record: MetadataRecord) -> None:
        self.logger.info(f"Publishing metadata: {record}")
        envelope = Envelope.from_metadata(record)
        payload = envelope.model_dump_json().encode()

        await self.producer.publish(payload)

    async def _wait_until_next_collection(self, wait_duration: float) -> None:
        self.logger.info(
            f"Waiting for {wait_duration:.4f} seconds before next collection..."
        )
        await asyncio.sleep(wait_duration)

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

        # Pause active surveys until we reconfigure
        await self.pause_survey()

        # Cancel current sweep task as it is no longer valid after a reconfig
        await self._cancel_sweep_task()

        if params:
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

        # Restart surveys if we were not told to pause
        if status != MonitorStatus.PAUSED:
            await self.start_survey()

    async def _queue_monitor(self):
        """Periodically logs the size of the processing queue."""
        self.logger.info("Queue monitor started.")
        try:
            while True:
                await asyncio.sleep(10)

                queue_size = self._processing_queue.qsize()

                if queue_size > (self._processing_queue.maxsize * 0.8):
                    self.logger.warning(
                        f"Processing queue is getting full! Size: {queue_size}/{self._processing_queue.maxsize}"
                    )
                else:
                    self.logger.info(
                        f"Processing queue size: {queue_size}/{self._processing_queue.maxsize}"
                    )

        except asyncio.CancelledError:
            self.logger.info("Queue monitor was cancelled and is shutting down.")
