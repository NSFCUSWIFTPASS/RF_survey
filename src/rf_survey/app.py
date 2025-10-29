import asyncio
import time
import signal

from rf_shared.nats_client import NatsProducer
from rf_shared.interfaces import ILogger

from rf_survey.heartbeat import IHeartbeatManager
from rf_survey.streamer import Streamer


class SurveyApp:
    """
    Encapsulates the state and logic for the RF Survey application.
    """

    def __init__(
        self,
        args,
        shutdown_event: asyncio.Event,
        streamer: Streamer,
        producer: NatsProducer,
        heartbeat_manager: IHeartbeatManager,
        logger: ILogger,
    ):
        self.args = args
        self.streamer = streamer
        self.producer = producer
        self.logger = logger
        self.shutdown_event = shutdown_event
        self.heartbeat_manager = heartbeat_manager

    def _signal_handler(self):
        """Sets the shutdown event when a signal is received."""
        if not self.shutdown_event.is_set():
            self.logger.info("Shutdown signal received. Signalling tasks to stop.")
            self.shutdown_event.set()

    async def run(self):
        """
        Initializes resources, runs the main application loop, and cleans up.
        """
        loop = asyncio.get_running_loop()
        tasks = []

        try:
            self.streamer.initialize()
            self.streamer.start_stream()
            await self.producer.connect()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._signal_handler)

            survey_task = asyncio.create_task(self._survey_runner())
            heartbeat_task = asyncio.create_task(self.heartbeat_manager.run())
            tasks.extend([survey_task, heartbeat_task])

            await asyncio.gather(*tasks)

        except Exception as e:
            self.logger.error(f"Critical error in run loop: {e}", exc_info=True)
            self.shutdown_event.set()

        finally:
            self.logger.info("Cleaning up resources...")

            for task in tasks:
                task.cancel()

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self.streamer.stop_stream()
            await self.producer.close()
            self.logger.info("Shutdown complete.")

    async def _survey_runner(self):
        if self.args.cycles == 0:
            while not self.shutdown_event.is_set():
                await self._perform_sweep()
        else:
            for i in range(self.args.cycles):
                if self.shutdown_event.is_set():
                    break
                self.logger.info(f"Starting sweep cycle {i+1}/{self.args.cycles}")
                await self._perform_sweep()

    async def _perform_sweep(self):
        """
        Performs a single sweep across the specified frequency range.
        """
        center_frequency_hz = self.args.frequency_start
        while (
            center_frequency_hz <= self.args.frequency_end
            and not self.shutdown_event.is_set()
        ):
            for _ in range(self.args.records):
                await self.streamer.wait_for_next_collection(self.shutdown_event)

                if self.shutdown_event.is_set():
                    break

                start_time = time.time()
                metadata_record = await self.streamer.receive_samples(
                    center_frequency_hz
                )
                end_time = time.time()

                self.logger.info(
                    f"Frequency step: {center_frequency_hz} Processing time: {end_time - start_time}"
                )

                await self.producer.publish_metadata(metadata_record)

                # Message heartbeat task that a sample was taken
                await self.heartbeat_manager.notify_sample_success()

            center_frequency_hz += self.args.bandwidth
