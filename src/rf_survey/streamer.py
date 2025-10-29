# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import uhd
import numpy as np
import asyncio
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rf_shared.models import MetadataRecord
from rf_shared.interfaces import ILogger
from rf_shared.checksum import get_checksum

from rf_survey.utils.scheduler import calculate_wait_time


class Streamer:
    def __init__(
        self,
        num_samples: int,
        bandwidth_hz: int,
        gain_db: int,
        interval_secs: int,
        max_jitter_secs: float,
        hostname: str,
        organization: str,
        coordinates: str,
        output_path: str,
        logger: ILogger,
    ):
        self.logger = logger

        self.path = Path(output_path)

        self.num_samples = num_samples
        self.bandwidth_hz = bandwidth_hz
        self.gain_db = gain_db

        capture_duration_sec = num_samples / self.bandwidth_hz
        self.margin = 0.2 / capture_duration_sec
        self.raw_sample_count = int(self.num_samples * (1 + self.margin))

        self.interval_secs = interval_secs
        self.max_jitter_secs = max_jitter_secs

        self.recv_buffer: Optional[np.ndarray] = None
        self.max_samps_per_chunk: int = 0
        self.samples = np.zeros(self.raw_sample_count, dtype=np.int32)

        self.hostname = hostname

        # Dictionary to create the metadata records
        self.md = {}
        self.md["hostname"] = self.hostname
        self.md["organization"] = organization
        self.md["gcs"] = coordinates
        self.md["interval"] = interval_secs
        self.md["length"] = capture_duration_sec
        self.md["gain"] = gain_db
        # bandwidth and sampling rate are always equal
        self.md["sampling_rate"] = self.bandwidth_hz
        self.md["bit_depth"] = 16
        self.md["group"] = str(uuid.uuid4())

    def initialize(self):
        """
        Connects to the USRP, configures it, and sets up the data stream.
        This method prepares the streamer to begin receiving samples.
        """
        try:
            self._connect_and_config_usrp()
            self._setup_stream()
        except (RuntimeError, KeyError) as e:
            self.logger.error(f"Failed to initialize USRP: {type(e).__name__}: {e}")
            raise

    def _connect_and_config_usrp(self):
        self.usrp = uhd.usrp.MultiUSRP("num_recv_frames=1024")
        self.usrp.set_rx_rate(self.bandwidth_hz, 0)
        self.usrp.set_rx_gain(self.gain_db, 0)
        self.usrp.set_rx_antenna("RX2", 0)  # can be either 'TX/RX' or 'RX2'

        self.serial = self.usrp.get_usrp_rx_info(0)["mboard_serial"]
        self.md["serial"] = self.serial

        # Check if external clock present:
        if "%s" % (self.usrp.get_mboard_sensor("ref_locked", 0)) != "Ref: unlocked":
            # Set the clock to an external source
            self.usrp.set_clock_source("external")
            self.usrp.set_time_source("external")

    def _setup_stream(self):
        # StreamArgs determine CPU and OTW data rates - sc16 = 16 bit signed integer
        st_args = uhd.usrp.StreamArgs("sc16", "sc16")
        st_args.channels = [0]
        self.rx_metadata = uhd.types.RXMetadata()
        self.streamer = self.usrp.get_rx_stream(st_args)
        self.max_samps_per_chunk = self.streamer.get_max_num_samps()
        self.recv_buffer = np.zeros((1, self.max_samps_per_chunk), dtype=np.int32)

    def _clear_buffers(self):
        assert self.recv_buffer is not None, "Streamer not properly initialized."
        self.recv_buffer.fill(0)
        self.samples.fill(0)

    def start_stream(self):
        # Start Stream in continuous mode
        stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
        stream_cmd.stream_now = True  # False #for external clock source
        # stream_cmd.time_spec = uhd.libpyuhd.types.time_spec(3.0) #3.0 needs to be tested
        self.streamer.issue_stream_cmd(stream_cmd)

    def stop_stream(self):
        """
        Closes the data stream.
        """
        stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
        self.streamer.issue_stream_cmd(stream_cmd)

    async def receive_samples(self, frequency: int) -> MetadataRecord:
        """
        Asynchronously executes the blocking SDR sampling and file I/O operations
        in a separate thread to avoid blocking the main event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._receive_samples_blocking, frequency
        )

    def _receive_samples_blocking(self, frequency: int) -> MetadataRecord:
        """
        Receives samples from the SDR at a specified frequency.
        """
        assert (
            self.streamer is not None and self.recv_buffer is not None
        ), "Streamer not properly initialized"
        self._clear_buffers()

        # Set frequency for current loop step
        self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(frequency), 0)

        # Generate timestamp for the filename
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.strftime("D%Y%m%dT%H%M%SM%f")

        sc16_path = self._build_filepath(timestamp_str)

        chunk_size = self.max_samps_per_chunk
        num_chunks = self.raw_sample_count // chunk_size

        # Receive the predetermined output of samples in groups of chunk size
        for i in range(num_chunks):
            self.streamer.recv(self.recv_buffer, self.rx_metadata)
            self.samples[i * chunk_size : (i + 1) * chunk_size] = self.recv_buffer[0]

        # Store the samples
        samples_to_discard = int(self.margin * self.num_samples)
        samples_to_write = self.samples[samples_to_discard:]

        data_bytes = samples_to_write.tobytes()
        file_checksum = get_checksum(data_bytes)
        self.logger.info(f"Calculated checksum: {file_checksum}")

        samples_to_write.tofile(sc16_path)
        self.logger.info(f"File stored as {sc16_path}")

        metadata_record = self._build_metadata_record(
            frequency=frequency,
            collection_time=timestamp,
            file_path=sc16_path,
            file_checksum=file_checksum,
        )

        return metadata_record

    async def wait_for_next_collection(self, shutdown_event: asyncio.Event):
        """
        Pauses execution until the next scheduled interval, plus a
        configurable random jitter.
        """
        jitter_duration = 0.0
        if self.max_jitter_secs > 0:
            jitter_duration = random.uniform(0, self.max_jitter_secs)

        base_wait_duration = calculate_wait_time(self.interval_secs)
        total_wait_duration = base_wait_duration + jitter_duration

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=total_wait_duration)
        except asyncio.TimeoutError:
            # This is the normal case: the wait finished without being interrupted.
            pass

        self.logger.info(
            f"Waiting for {total_wait_duration:.4f} seconds "
            f"(base: {base_wait_duration:.4f} + jitter: {jitter_duration:.4f})...",
        )

    # XXX: Does this even work?
    def calculate_optimal_gain(self, gain):
        """
        Calculates optimal gain for receiver.
        """
        assert (
            self.streamer is not None and self.recv_buffer is not None
        ), "Streamer not properly initialized"

        self.usrp.set_rx_gain(gain, 0)
        print(gain)
        for i in range(self.num_samples // self.max_samps_per_chunk):
            self.streamer.recv(self.recv_buffer, self.rx_metadata)
            self.samples[
                i * self.max_samps_per_chunk : (i + 1) * self.max_samps_per_chunk
            ] = self.recv_buffer[0]

        data = self.samples.view(np.int16)
        dataset = np.zeros(int(len(data) / 2))
        dataset = data[0::2] + 1j * data[1::2]

        real = np.max(dataset.real)
        imag = np.max(dataset.imag)
        count_real = np.count_nonzero(dataset.real == 32767.0)
        count_imag = np.count_nonzero(dataset.imag == 32767.0)
        values = [real, imag, count_real, count_imag]
        return values

    def _build_filepath(self, timestamp_str: str) -> Path:
        """
        Constructs the full file path for an IQ data file using a given timestamp.
        """
        filename = f"{self.serial}-{self.hostname}-{timestamp_str}.sc16"

        return self.path / filename

    def _build_metadata_record(
        self,
        frequency: int,
        collection_time: datetime,
        file_path: Path,
        file_checksum: str,
    ) -> MetadataRecord:
        """
        Factory method to assemble a MetadataRecord from the streamer's static
        configuration and the dynamic data from a single collection.
        """
        data = self.md.copy()

        data["frequency"] = frequency
        data["timestamp"] = collection_time
        data["source_path"] = file_path
        data["checksum"] = file_checksum

        return MetadataRecord(**data)
