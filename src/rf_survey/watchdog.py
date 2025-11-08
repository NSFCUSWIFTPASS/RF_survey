import asyncio
import time
from typing import Optional

from rf_shared.interfaces import ILogger


class WatchdogTimeoutError(Exception):
    """Raised when the application watchdog times out."""

    pass


class ApplicationWatchdog:
    """
    A watchdog to monitor the liveness of the main application loop.
    Watchdog is disabled if timeot_seconds is None.
    """

    def __init__(
        self,
        timeout_seconds: Optional[float],
        logger: ILogger,
    ):
        self.timeout_seconds = timeout_seconds
        self.logger = logger

        # Internal state
        self._last_pet_time: float = time.monotonic()
        self._is_paused: bool = False
        self._lock = asyncio.Lock()

    async def run(self):
        """
        The main execution loop for the watchdog.
        Checks periodically if the application has recently been "pet".
        """
        if self.timeout_seconds is None or self.timeout_seconds <= 0:
            self.logger.info("Application watchdog is disabled by configuration.")
            return

        self.logger.info(
            f"Application watchdog started with a {self.timeout_seconds:.2f}s timeout."
        )

        check_interval_secs = 5.0

        try:
            while True:
                await asyncio.sleep(check_interval_secs)

                async with self._lock:
                    if self._is_paused:
                        self.logger.debug(
                            "Watchdog is paused. Skipping liveness check."
                        )
                        continue

                    time_since_last_pet = time.monotonic() - self._last_pet_time

                    if time_since_last_pet > self.timeout_seconds:
                        self.logger.critical(
                            f"WATCHDOG TIMEOUT: Application has not been pet in {time_since_last_pet:.2f}s "
                            f"(limit: {self.timeout_seconds:.2f}s). Initiating graceful shutdown."
                        )
                        raise WatchdogTimeoutError

        except asyncio.CancelledError:
            self.logger.info("Watchdog was cancelled.")

        finally:
            self.logger.info("Application watchdog is shutting down.")

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
            if not self._is_paused:
                self.logger.warning("Application watchdog is being PAUSED.")
                self._is_paused = True

    async def resume(self):
        """
        Resumes the watchdog and resets its timer.
        Should be called when the application leaves a long-wait state.
        """
        if self.timeout_seconds is None:
            return

        async with self._lock:
            if self._is_paused:
                self.logger.info("Application watchdog is being RESUMED.")
                self._is_paused = False
                self._last_pet_time = time.monotonic()
