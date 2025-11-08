import uhd
import numpy as np
import asyncio
import time
import threading
from datetime import datetime, timezone
from copy import deepcopy

from rf_shared.interfaces import ILogger

from rf_survey.models import RawCapture, ReceiverConfig, CaptureResult


class Receiver:
    def __init__(
        self,
        receiver_config: ReceiverConfig,
        logger: ILogger,
    ):
        self.logger = logger
        self._hardware_lock = threading.Lock()

        self.config = receiver_config

    def initialize(self) -> None:
        """Connects to and fully configures the USRP hardware and stream."""
        try:
            self._initialize_hardware()
        except (RuntimeError, KeyError) as e:
            self.logger.error(f"Failed to initialize USRP: {type(e).__name__}: {e}")
            raise

    def _initialize_hardware(self) -> None:
        """
        Connects to the USRP, configures all hardware parameters,
        and sets up the data stream and buffers.
        """
        self.logger.info("Initializing USRP hardware and stream...")

        self.usrp = uhd.usrp.MultiUSRP("num_recv_frames=1024")
        self.usrp.set_rx_rate(self.config.bandwidth_hz, 0)
        self.usrp.set_rx_gain(self.config.gain_db, 0)
        self.usrp.set_rx_antenna("RX2", 0)

        self.serial = self.usrp.get_usrp_rx_info(0)["mboard_serial"]

        if "%s" % (self.usrp.get_mboard_sensor("ref_locked", 0)) != "Ref: unlocked":
            self.logger.info("Setting clock from external source")
            self.usrp.set_clock_source("external")
            self.usrp.set_time_source("external")
        else:
            self.logger.info("Setting clock to host time")
            self.usrp.set_time_now(uhd.types.TimeSpec(time.time()))

        st_args = uhd.usrp.StreamArgs("sc16", "sc16")
        st_args.channels = [0]
        self.rx_metadata = uhd.types.RXMetadata()
        self.rx_streamer = self.usrp.get_rx_stream(st_args)

        self.logger.info("USRP hardware initialization complete.")

    async def reconfigure(self, new_config: ReceiverConfig) -> None:
        """
        Asynchronously triggers a thread-safe, blocking reconfiguration of the hardware.
        """
        loop = asyncio.get_running_loop()
        self.logger.info("Scheduling hardware reconfiguration...")

        await loop.run_in_executor(
            None,
            self._reconfigure_blocking,
            new_config,
        )

        self.logger.info("Hardware reconfiguration has completed.")

    def _reconfigure_blocking(self, new_config: ReceiverConfig) -> None:
        with self._hardware_lock:
            self.logger.info("Hardware lock acquired. Applying new configuration...")

            self.config = new_config
            self.rx_streamer = None

            self._initialize_hardware()

            self.logger.info("Reconfiguration complete and lock released.")

    async def receive_samples(self, center_freq_hz: int) -> CaptureResult:
        """
        Asynchronously executes the blocking SDR sampling and file I/O operations
        in a separate thread to avoid blocking the main event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._receive_samples_blocking, center_freq_hz
        )

    def _receive_samples_blocking(self, center_freq_hz: int) -> CaptureResult:
        """
        Receives samples from the SDR at a specified frequency.
        """
        assert self.rx_streamer is not None, "Streamer not properly initialized"

        with self._hardware_lock:
            config_at_capture = deepcopy(self.config)

            # Set frequency for current loop step
            self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(center_freq_hz), 0)

            samples_to_collect = self.config.num_samples
            capture_buffer = np.zeros(samples_to_collect, dtype=np.int32)
            rx_metadata = uhd.types.RXMetadata()

            # Wait for lo to settle instead of over sampling and discarding a margin
            self._wait_for_settle_lo()

            stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.num_done)
            stream_cmd.num_samps = samples_to_collect
            stream_cmd.stream_now = True
            self.rx_streamer.issue_stream_cmd(stream_cmd)

            try:
                # Use a timeout slightly longer than the expected capture duration
                timeout = self.config.duration_sec + 2.0

                capture_timestamp = datetime.now(timezone.utc)

                start_recv = time.monotonic()
                samples_received = self.rx_streamer.recv(
                    capture_buffer, rx_metadata, timeout=timeout
                )
                recv_duration = time.monotonic() - start_recv

                self.logger.info(
                    f"recv() call returned after {recv_duration:.3f} seconds."
                )

            except RuntimeError as e:
                self.logger.error(f"A UHD recv error occurred: {e}", exc_info=True)
                raise

            if rx_metadata.error_code != uhd.types.RXMetadataErrorCode.none:
                raise RuntimeError(
                    f"UHD recv completed with error: {rx_metadata.strerror()}"
                )

            if samples_received < samples_to_collect:
                raise RuntimeError(
                    f"Capture truncated: expected {samples_to_collect}, received {samples_received}"
                )

            # This needs to be tested further, it seems it can drift
            # capture_timestamp = self._get_timestamp(rx_metadata)

            raw_capture = RawCapture(
                iq_data_bytes=capture_buffer.tobytes(),
                center_freq_hz=center_freq_hz,
                capture_timestamp=capture_timestamp,
            )

            result = CaptureResult(
                raw_capture=raw_capture, receiver_config=config_at_capture
            )

            return result

    def _get_timestamp(self, rx_metadata: uhd.types.RXMetadata) -> datetime:
        # Get timestamp from rx_metadata if possible
        if rx_metadata.has_time_spec:
            ts_int = rx_metadata.time_spec.get_full_secs()
            ts_frac = rx_metadata.time_spec.get_frac_secs()

            precise_timestamp = datetime.fromtimestamp(
                ts_int + ts_frac, tz=timezone.utc
            )
            self.logger.debug(
                f"Using precise hardware timestamp: {precise_timestamp.isoformat()}"
            )
        else:
            # Fallback in case the hardware/driver doesn't provide a timestamp.
            self.logger.warning(
                "RX metadata did not contain a time spec. Falling back to software timestamp."
            )
            precise_timestamp = datetime.now(timezone.utc)

        return precise_timestamp

    def _wait_for_settle_lo(self):
        max_lock_wait_sec = 1.0
        start_wait = time.monotonic()
        while not self.usrp.get_rx_sensor("lo_locked", 0).to_bool():
            if time.monotonic() - start_wait > max_lock_wait_sec:
                self.logger.error(
                    f"USRP failed to lock LO at target frequency within {max_lock_wait_sec}s."
                )
                break

        lock_time = time.monotonic() - start_wait
        self.logger.debug(f"LO locked in {lock_time * 1000:.2f} ms.")
