# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import uhd
import numpy as np
import os
import time
import math
from dateutil.relativedelta import relativedelta
from datetime import datetime
import random
import json
import pickle
from gpiozero import CPUTemperature
import subprocess
from subprocess import DEVNULL
import sys
import uuid
from Logger import Logger

class Streamer(object):
    def __init__(self, num_samps, center_freq_start, sample_rate, gain, interval, length, hostname, organization, coordinates, group):
        log_time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"]+"/logs/"
        self.logger = Logger("streamer", log_path, "stream-"+log_time+".log")

        self.hostname = hostname
        self.path = "/mnt/datab-netStorage-1G/sync/" #"/home/pi/sync/"          # path where IQ data will be stored
        self.dict = {}
        self.margin = 0.2/float(length)

         # get the host's hostname
        self.num_samps = num_samps
        self.inc_samps = int(self.num_samps*(1+self.margin))                                              # number of samples received
        self.samples = np.zeros(self.inc_samps, dtype=np.int32)
        self.bandwidth = sample_rate                                            # bandwidth and sampling rate are always equal
        self.gain_setting = gain

        try:
            self.usrp = uhd.usrp.MultiUSRP("num_recv_frames=1024")
            self.usrp.set_rx_rate(sample_rate, 0)
            self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(center_freq_start), 0)
            # The receive frequency can be changed to use an offset frequency by using the line below instead
            #self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(center_freq, offset), 0)

            # Sets the receive gain value
            self.usrp.set_rx_gain(gain, 0)

            # UHD supports activating the agc, DO NOT USE, this is only for informational purposes
            #self.usrp.set_rx_agc(True, 0)

            # Choose the antenna port, either 'TX/RX' or 'RX2'
            self.usrp.set_rx_antenna('RX2', 0)

            # Get SDR serial number
            self.serial = self.usrp.get_usrp_rx_info(0)['mboard_serial']
        except:
            self.logger.write_log("ERROR","USRP is not connected: %s" % (repr(e)))
            return

        # Check if external clock present:
        if "%s"%(self.usrp.get_mboard_sensor("ref_locked", 0)) != "Ref: unlocked":
            # Set the clock to an external source
            self.usrp.set_clock_source("external")
            self.usrp.set_time_source("external")

        # Dictionary to create the metadata file containing essential information
        self.md ={}
        self.md['hostname'] = self.hostname
        self.md['serial'] = self.serial
        self.md['organization'] = organization
        self.md['gcs'] = coordinates
        self.md['frequency'] = center_freq_start
        self.md['interval'] = int(interval)
        self.md['length'] = length
        self.md['gain'] = gain
        self.md['sampling_rate'] = sample_rate
        self.md['bit_depth']= 16
        self.md['group'] = group
        #self.md['average'] = 0
        #self.md['flag'] = 1
        self.status = {}
        self.status['hostname'] = self.hostname                                                 # change to 32 for fc32

    def setup_stream(self):
        # Set up the stream and receive buffer

        # StreamArgs determine CPU and OTW data rates - sc16 = 16 bit signed integer
        st_args = uhd.usrp.StreamArgs("sc16", "sc16")
        st_args.channels = [0]
        self.metadata = uhd.types.RXMetadata()
        self.streamer = self.usrp.get_rx_stream(st_args)
        self.buffer = self.streamer.get_max_num_samps()                         # determines buffer size
        self.recv_buffer = np.zeros((1, self.buffer), dtype=np.int32)           # needs to be 2xStreamArgs, e.g sc16 -> np.int32

    def start_stream(self):

        # Start Stream in continuous mode
        stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
        stream_cmd.stream_now = True #set to False if using external clock source
        self.streamer.issue_stream_cmd(stream_cmd)
        self.status['hardware_op_status'] = 2

    def receive_samples(self, frequency):
        # Receives samples from the SDR

        # Generate White Rabbit status updates
        if os.path.exists(os.environ["HOME"]+"/wr_poll.py"):
            process = subprocess.Popen("python2 /home/pi/wr_poll.py", shell=True, stdout=DEVNULL)
        else:
            self.logger.write_log("DEBUG","No WR-LEN present.")

        # New buffer
        self.recv_buffer = np.zeros((1, self.buffer), dtype=np.int32)

        # Set frequency for current loop step
        self.usrp.set_rx_freq(uhd.libpyuhd.types.tune_request(frequency), 0)
        self.md['frequency'] = frequency

        # Generate timestamp for the filename
        now = datetime.now()
        self.timestamp = now.strftime('D%Y%m%dT%H%M%SM%f')
        self.status['time'] = time.strftime("%Y-%m-%d %H:%M:%S %z")

        # Receive the predetermined output of samples in groups of buffer size
        for i in range(self.inc_samps//self.buffer):
            self.streamer.recv(self.recv_buffer, self.metadata)
            self.samples[i*self.buffer:(i+1)*self.buffer] = self.recv_buffer[0]
        # Store the samples and metadata file
        self.samples[int(self.margin*self.num_samps):].tofile(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+".sc16"))
        #os.chmod(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+".sc16"), 0o777)

        # Get SDR temperature and RSSI
        self.md['temperature (C)'] = float(str(self.usrp.get_rx_sensor("temp", 0))[6:-2])
        self.md['rssi (dB)'] = float(str(self.usrp.get_rx_sensor("rssi", 0))[6:-2])
        with open(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+".json"),"w") as outfile:
            json.dump(self.md, outfile)
        #os.chmod(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+".json"), 0o777)
        self.logger.write_log("INFO","File stored as %s."%(self.serial+"-"+self.hostname+"-"+self.timestamp))

        # Collect and store status information
        self.status['bytes_recorded'] = len(self.samples[int(self.margin*self.num_samps):])
        try:
            self.status['sdr_temp'] = float(str(self.usrp.get_rx_sensor("temp", 0))[6:-2])
            self.status['sdr_op_status'] = 1
        except Exception as e:
            self.logger.write_log("CRITICAL","Failed to connect to sdr with: %s"%(repr(e)))
            self.status['sdr_temp'] = None
            self.status['sdr_op_status'] = 1
        self.status['rpi_cpu_temp'] = CPUTemperature().temperature
        self.status['avg_cpu_usage'] = os.getloadavg()[2]/os.cpu_count() * 100
        self.status['rem_rpi_storage_cap'] = int(str(subprocess.check_output("df | grep -i 'root' | awk '{print $2}'", shell=True))[2:-3])
        self.status['rpi_uptime(minutes)'] = int(float(str(subprocess.check_output("echo $(awk '{print $1}' /proc/uptime)", shell=True))[2:-3])/60)
        self.status['rpi_op_status'] = 1
        try:
            with open("/home/pi/wr_dynamic.json", "r") as f:
                wr = json.load(f)

            self.status['wr_temp'] = wr['temp']
            self.status['wr0_rx'] = wr['wr0_rx']
            self.status['wr0_tx'] = wr['wr0_tx']
            self.status['wr1_rx'] = wr['wr1_rx']
            self.status['wr1_tx'] = wr['wr1_tx']
            self.status['wr0_lnk'] = str(wr['wr0_lnk'])
            self.status['wr1_lnk'] = str(wr['wr1_lnk'])
            self.status['wr0_setp'] = wr['wr0_setp']
            self.status['wr0_cko'] = wr['wr0_cko']
            self.status['wr0_mu'] = wr['wr0_mu']
            self.status['wr0_crtt'] = wr['wr0_crtt']
            self.status['wr0_ucnt'] = wr['wr0_ucnt']
            self.status['wr0_ss'] = wr['wr0_ss'].replace("'", "")
            self.status['serial'] = wr['serial']
            self.status['wr_host'] = wr['wr_host']
            self.status['wr_op_status'] = wr['wr_op_status']
        except:
            self.status['wr_temp'] = None
            self.status['wr0_rx'] = None
            self.status['wr0_tx'] = None
            self.status['wr1_rx'] = None
            self.status['wr1_tx'] = None
            self.status['wr0_lnk'] = None
            self.status['wr1_lnk'] = None
            self.status['wr0_setp'] = None
            self.status['wr0_cko'] = None
            self.status['wr0_mu'] = None
            self.status['wr0_crtt'] = None
            self.status['wr0_ucnt'] = None
            self.status['wr0_ss'] = None
            self.status['serial'] = ""
            self.status['wr_host'] = ""
            self.status['wr_op_status'] = 0

        with open(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+"-status.json"),"w") as outfile:
            json.dump(self.status, outfile)
        #os.chmod(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+"-status.json"), 0o777)

        # Clear buffer
        self.recv_buffer = None

    def receive_gain(self, gain):
        # used to select an optimal gain setting
        self.usrp.set_rx_gain(gain, 0)
        print(gain)
        for i in range(self.num_samps//self.buffer):
            self.streamer.recv(self.recv_buffer, self.metadata)
            self.samples[i*self.buffer:(i+1)*self.buffer] = self.recv_buffer[0]

        data = self.samples.view(np.int16)
        dataset = np.zeros(int(len(data)/2))
        dataset = data[0::2] + 1j*data[1::2]

        real = np.max(dataset.real)
        imag = np.max(dataset.imag)
        count_real = np.count_nonzero(dataset.real == 32767.0)
        count_imag = np.count_nonzero(dataset.imag == 32767.0)
        values = [real, imag, count_real, count_imag]
        return(values)

    def stop_stream(self):
        # Closes the data stream
        stream_cmd = uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont)
        self.streamer.issue_stream_cmd(stream_cmd)
        if self.gain_setting == 0:
            with open('values.pickle', 'wb') as outfile:
                pickle.dump(self.dict, outfile)

        self.status['hardware_op_status'] = 1

        with open(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+"-status.json"),"w+") as outfile:
            json.dump(self.status, outfile)
        #os.chmod(str(self.path+self.serial+"-"+self.hostname+"-"+self.timestamp+"-status.json"), 0o777)

    def timer(self, seconds):
        # Timer for regular intervals - calculates time to next interval and increments time
        t = datetime.today()
        if int(math.floor(seconds)) >= 1:
            seconds = int(seconds)
            next_interval = (t.second//seconds + 1) * seconds
            if next_interval >= 60:
                next_second = ((t.minute * 60 + t.second) // next_interval + 1) * next_interval % 60
                minutes = next_interval // 60
                next_minute = abs(t.minute - ((t.minute // minutes + 1) * minutes))
                future = datetime(t.year, t.month, t.day, t.hour, t.minute, next_second, 0) + relativedelta(minutes=+next_minute)
            else:
                next_second = next_interval
                future = datetime(t.year, t.month, t.day, t.hour, t.minute, next_second, 0)
        else:
            microsecond = int(seconds * 1000000)
            print(t.microsecond)
            next_microsecond = (t.microsecond//microsecond + 1) * microsecond
            if next_microsecond >= 1000000:
                next_microsecond = next_microsecond - 1000000
                future = datetime(t.year, t.month, t.day, t.hour, t.minute, t.second, next_microsecond) + relativedelta(seconds=+1)
            else:
                future = datetime(t.year, t.month, t.day, t.hour, t.minute, t.second, next_microsecond)
        self.logger.write_log("INFO","Wait time: %s"%((future-t).total_seconds()))
        time.sleep((future-datetime.today()).total_seconds())

    def rand_timer(self, maxtimer):
        # Random timer with lower and upper bounds
        maxtime = maxtimer
        mintime = np.ceil(self.bandwidth/1e6 * 0.2)
        if maxtime <= mintime:
            raise ValueError()
        t = datetime.today()
        interval = random.randint(mintime, maxtime)
        future = t + relativedelta(seconds = interval)
        self.logger.write_log("INFO","Wait time: %s"%((future-t).total_seconds()))
        time.sleep((future-t).total_seconds())
