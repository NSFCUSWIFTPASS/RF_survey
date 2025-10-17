import asyncio
import time
import signal

from rf_shared.nats_client import NatsProducer
from rf_shared.interfaces import ILogger

from rf_survey.streamer import Streamer


class SurveyApp:
    """
    Encapsulates the state and logic for the RF Survey application.
    """

    def __init__(
        self, args, streamer: Streamer, producer: NatsProducer, logger: ILogger
    ):
        self.args = args
        self.streamer = streamer
        self.producer = producer
        self.logger = logger
        self.shutdown_event = asyncio.Event()

    def _signal_handler(self):
        """Sets the shutdown event when a signal is received."""
        if not self.shutdown_event.is_set():
            self.logger.info("Shutdown signal received. Signalling tasks to stop.")
            self.shutdown_event.set()

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
                metadata_record = self.streamer.receive_samples(center_frequency_hz)
                end_time = time.time()

                self.logger.info(
                    f"Frequency step: {center_frequency_hz} Processing time: {end_time - start_time}"
                )

                await self.producer.publish_metadata(metadata_record)

            center_frequency_hz += self.args.bandwidth

    async def run(self):
        """
        Initializes resources, runs the main application loop, and cleans up.
        """
        loop = asyncio.get_running_loop()
        try:
            self.streamer.initialize()
            self.streamer.start_stream()
            await self.producer.connect()

            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._signal_handler)

            # Main app loop
            if self.args.cycles == 0:
                while not self.shutdown_event.is_set():
                    await self._perform_sweep()
            else:
                for i in range(self.args.cycles):
                    if self.shutdown_event.is_set():
                        break
                    self.logger.info(f"Starting sweep cycle {i+1}/{self.args.cycles}")
                    await self._perform_sweep()

        except Exception as e:
            self.logger.error(f"Critical error in run loop: {e}", exc_info=True)

        finally:
            self.logger.info("Cleaning up resources...")
            self.streamer.stop_stream()
            await self.producer.close()
            self.logger.info("Shutdown complete.")
