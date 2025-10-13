# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import uhd
import numpy as np
import os
import time
from datetime import datetime
import random


from utils.scheduler import calculate_wait_time
from utils.logger import Logger


class Streamer(object):
    def __init__(
        self,
        num_samps,
        center_freq_start,
        sample_rate,
        gain,
        interval,
        jitter,
        length,
        hostname,
        organization,
        coordinates,
        group,
    ):
        log_time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"] + "/logs/"
        self.logger = Logger("streamer", log_path, "stream-" + log_time + ".log")

        self.hostname = hostname
        self.path = "/mnt/net-sync/"  # "/mnt/net-sync/" #"/home/pi/sync/"          # path where IQ data will be stored
        self.dict = {}
        self.margin = 0.2 / float(length)

        self.interval = interval
        self.jitter = jitter

        # get the host's hostname
        self.num_samps = num_samps
        self.inc_samps = int(
            self.num_samps * (1 + self.margin)
        )  # number of samples received
        self.samples = np.zeros(self.inc_samps, dtype=np.int32)
        self.bandwidth = sample_rate  # bandwidth and sampling rate are always equal
        self.gain_setting = gain

        try:
            self.usrp = uhd.usrp.MultiUSRP("num_recv_frames=1024")
            self.usrp.set_rx_rate(sample_rate, 0)
            self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(center_freq_start), 0)
            # The receive frequency can be changed to use an offset frequency by using the line below instead
            # self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(center_freq, offset), 0)

            # Sets the receive gain value
            self.usrp.set_rx_gain(gain, 0)

            # UHD supports activating the agc, DO NOT USE, this is only for informational purposes
            # self.usrp.set_rx_agc(True, 0)

            # Choose the antenna port, either 'TX/RX' or 'RX2'
            self.usrp.set_rx_antenna("RX2", 0)

            # Get SDR serial number
            self.serial = self.usrp.get_usrp_rx_info(0)["mboard_serial"]
        except:
            logger.write_log("ERROR", "USRP is not connected: %s" % (repr(e)))
            return

        # Check if external clock present:
        if "%s" % (self.usrp.get_mboard_sensor("ref_locked", 0)) != "Ref: unlocked":
            # Set the clock to an external source
            self.usrp.set_clock_source("external")
            self.usrp.set_time_source("external")

        # Dictionary to create the metadata file containing essential information
        self.md = {}
        self.md["hostname"] = self.hostname
        self.md["serial"] = self.serial
        self.md["organization"] = organization
        self.md["gcs"] = coordinates
        self.md["frequency"] = center_freq_start
        self.md["interval"] = int(interval)
        self.md["length"] = length
        self.md["gain"] = gain
        self.md["sampling_rate"] = sample_rate
        self.md["bit_depth"] = 16
        self.md["group"] = group
        # self.md['average'] = 0
        # self.md['flag'] = 1
        self.status = {}
        self.status["hostname"] = self.hostname  # change to 32 for fc32

    def setup_stream(self):
        # Set up the stream and receive buffer

        # StreamArgs determine CPU and OTW data rates - sc16 = 16 bit signed integer
        st_args = uhd.usrp.StreamArgs("sc16", "sc16")
        st_args.channels = [0]
        self.metadata = uhd.types.RXMetadata()
        self.streamer = self.usrp.get_rx_stream(st_args)
        self.buffer = self.streamer.get_max_num_samps()  # determines buffer size
        # print(self.buffer)
        self.recv_buffer = np.zeros(
            (1, self.buffer), dtype=np.int32
        )  # needs to be 2xStreamArgs, e.g sc16 -> np.int32

    def start_stream(self):
        # Start Stream in continuous mode
        stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
        stream_cmd.stream_now = True  # False #for external clock source
        # stream_cmd.time_spec = uhd.libpyuhd.types.time_spec(3.0) #3.0 needs to be tested
        self.streamer.issue_stream_cmd(stream_cmd)
        self.status["hardware_op_status"] = 2

    def receive_samples(self, frequency):
        # Receives samples from the SDR

        # New buffer
        self.recv_buffer = np.zeros((1, self.buffer), dtype=np.int32)

        # Set frequency for current loop step
        self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(frequency), 0)
        self.md["frequency"] = frequency

        # Generate timestamp for the filename
        now = datetime.now()
        self.timestamp = now.strftime("D%Y%m%dT%H%M%SM%f")
        self.status["time"] = time.strftime("%Y-%m-%d %H:%M:%S %z")

        # Receive the predetermined output of samples in groups of buffer size
        for i in range(self.inc_samps // self.buffer):
            self.streamer.recv(self.recv_buffer, self.metadata)
            self.samples[i * self.buffer : (i + 1) * self.buffer] = self.recv_buffer[0]

        # Store the samples and metadata file
        self.samples[int(self.margin * self.num_samps) :].tofile(
            str(
                self.path
                + self.serial
                + "-"
                + self.hostname
                + "-"
                + self.timestamp
                + ".sc16"
            )
        )

        self.logger.write_log(
            "INFO",
            "File stored as %s."
            % (self.serial + "-" + self.hostname + "-" + self.timestamp),
        )

        # Clear buffer
        self.recv_buffer = None

    def receive_gain(self, gain):
        # used to select an optimal gain setting
        self.usrp.set_rx_gain(gain, 0)
        print(gain)
        for i in range(self.num_samps // self.buffer):
            self.streamer.recv(self.recv_buffer, self.metadata)
            self.samples[i * self.buffer : (i + 1) * self.buffer] = self.recv_buffer[0]

        data = self.samples.view(np.int16)
        dataset = np.zeros(int(len(data) / 2))
        dataset = data[0::2] + 1j * data[1::2]

        real = np.max(dataset.real)
        imag = np.max(dataset.imag)
        count_real = np.count_nonzero(dataset.real == 32767.0)
        count_imag = np.count_nonzero(dataset.imag == 32767.0)
        values = [real, imag, count_real, count_imag]
        return values

    def stop_stream(self):
        # Closes the data stream
        stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
        self.streamer.issue_stream_cmd(stream_cmd)

    def wait_for_next_collection(self):
        """
        Pauses execution until the next scheduled interval, plus a
        configurable random jitter.
        """
        jitter_duration = 0.0
        if self.jitter > 0:
            jitter_duration = random.uniform(0, self.jitter)

        base_wait_duration = calculate_wait_time(self.interval)
        total_wait_duration = base_wait_duration + jitter_duration

        time.sleep(total_wait_duration)

        self.logger.write_log(
            "INFO",
            f"Waiting for {total_wait_duration:.4f} seconds "
            f"(base: {base_wait_duration:.4f} + jitter: {jitter_duration:.4f})...",
        )
