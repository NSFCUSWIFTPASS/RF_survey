import asyncio
import datetime
import logging
import threading
import numpy as np

from rf_survey.models import ReceiverConfig, RawCapture, CaptureResult

logger = logging.getLogger(__name__)


class Receiver:
    """
    A drop-in mock replacement for the real hardware Receiver class that
    matches the new, simplified, and thread-safe API.
    """

    def __init__(
        self,
        receiver_config: ReceiverConfig,
        **kwargs,
    ):
        self.config = receiver_config
        self._hardware_lock = threading.Lock()
        self.serial = "MOCK-SERIAL-123"
        self.hostname = "mock-host"  # Needed for processing step
        logger.info("--- MockReceiver created ---")
        logger.info(f"Initial configuration: {self.config}")

    def initialize(self) -> None:
        """Simulates the one-time hardware initialization."""
        logger.info("MockReceiver: initialize() called.")

    async def reconfigure(self, new_config: ReceiverConfig) -> None:
        """Simulates applying a new configuration."""
        logger.info(f"MockReceiver: reconfigure() called with new config: {new_config}")
        with self._hardware_lock:
            logger.info("Simulating hardware hard reset delay...")
            await asyncio.sleep(0.1)  # Simulate the blocking part
            self.config = new_config
            logger.info("MockReceiver: Reconfiguration complete.")

    async def receive_samples(self, center_freq_hz: int) -> CaptureResult:
        """
        Simulates capturing samples for the configured duration.
        Returns a RawCapture object.
        """
        logger.info(
            f"MockReceiver: receive_samples() for frequency {center_freq_hz / 1e6:.2f} MHz."
        )
        with self._hardware_lock:
            # Simulate the blocking work of a capture
            capture_duration = self.config.duration_sec
            logger.debug(f"Simulating a capture of {capture_duration:.3f} seconds...")
            await asyncio.sleep(capture_duration)

            logger.info("MockReceiver: Capture complete. Building RawCapture object.")

            # Create a buffer of fake data with the correct size and dtype
            mock_buffer = np.zeros(self.config.num_samples, dtype=np.int32)

            raw_capture = RawCapture(
                iq_data_bytes=mock_buffer.tobytes(),
                center_freq_hz=center_freq_hz,
                # For now, use datetime.now() as requested.
                capture_timestamp=datetime.datetime.now(datetime.timezone.utc),
            )

            return CaptureResult(raw_capture, self.config)
