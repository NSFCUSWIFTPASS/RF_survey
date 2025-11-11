import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class WatchdogTimeoutError(Exception):
    """Raised when the application watchdog times out."""

    pass


class ApplicationWatchdog:
    """
    A watchdog to monitor the liveness of the main application loop.
    Watchdog is disabled if timeout_seconds is None.
    """

    def __init__(
        self,
        timeout_seconds: Optional[float],
    ):
        self.timeout_seconds = timeout_seconds

        # Internal state
        self._last_pet_time: float = time.monotonic()
        self._running_event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def run(self):
        """
        The main execution loop for the watchdog.
        Checks periodically if the application has recently been "pet".
        """
        if self.timeout_seconds is None or self.timeout_seconds <= 0:
            logger.info("Application watchdog is disabled by configuration.")
            return

        logger.info(
            f"Application watchdog started with a {self.timeout_seconds:.2f}s timeout."
        )

        check_interval_secs = 5.0

        try:
            while True:
                await asyncio.sleep(check_interval_secs)

                async with self._lock:
                    if not self._running_event.is_set():
                        logger.debug("Watchdog is paused. Skipping liveness check.")
                        continue

                    time_since_last_pet = time.monotonic() - self._last_pet_time

                    if time_since_last_pet > self.timeout_seconds:
                        logger.critical(
                            f"WATCHDOG TIMEOUT: Application has not been pet in {time_since_last_pet:.2f}s "
                            f"(limit: {self.timeout_seconds:.2f}s). Initiating graceful shutdown."
                        )
                        raise WatchdogTimeoutError

        except asyncio.CancelledError:
            logger.info("Watchdog was cancelled.")

        finally:
            logger.info("Application watchdog is shutting down.")

    async def pet(self):
        """
        Resets the watchdog timer, signaling that the application is alive.
        """
        if self.timeout_seconds is None:
            return

        async with self._lock:
            self._last_pet_time = time.monotonic()

    async def pause(self):
        """
        Pauses the watchdog, preventing it from timing out.
        Should be called when the application enters a legitimate long-wait state.
        """
        if self.timeout_seconds is None:
            return

        async with self._lock:
            if self._running_event.is_set():
                logger.warning("Application watchdog is being PAUSED.")
                self._running_event.clear()

    async def start(self):
        """
        Starts the watchdog and resets its timer.
        Should be called when the application leaves a long-wait state.
        """
        if self.timeout_seconds is None:
            return

        async with self._lock:
            if not self._running_event.is_set():
                logger.info("Application watchdog is being STARTED.")
                self._running_event.set()
                self._last_pet_time = time.monotonic()
