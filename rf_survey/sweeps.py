# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import numpy as np
import time
import os
import subprocess
import argparse
import sys
import random
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from Streamer import Streamer
from Logger import Logger
from GracefulKiller import GracefulKiller
from Cronify import Cronify
from Restoration import Restoration

#####################################################
# The streamer class contains all functions related #
# to running the I/Q data collection stream.        #
#####################################################

def group_number(length=6):
    group = ''
    for i in range(length):
        random_integer = random.randint(97, 97 +26 - 1)
        flip_bit = random.randint(0, 1)
        random_integer = random_integer - 32 if flip_bit == 1 else random_integer
        group +=(chr(random_integer))
    return group

def gain_check(g):
    num = int(g)

    if num < 0 or num > 76:
        raise argparse.ArgumentTypeError("Valid gain values range from 0 to 76")
    return num

def sleep(seconds, grace):
    now = time.monotonic()
    end = now+seconds
    for i in range(int(seconds)):
        if grace.kill_now:
            sys.exit(0)
        elif time.monotonic()+1 <= end:
            time.sleep(1)
        else:
            time.sleep(end - time.monotonic())
            break

def cleanup():
    if os.path.exists(os.environ["HOME"]+"/rf_survey.pid"):
        os.remove(os.environ["HOME"]+"/rf_survey.pid")
    if os.path.exists(os.environ["HOME"]+"/lifesigns.json"):
        os.remove(os.environ["HOME"]+"/lifesigns.json")
    cronjob = Cronify()
    cronjob.delete_job()

def main():
    log_time = datetime.now().strftime("%Y-%m-%d")
    log_path = os.environ["HOME"]+"/logs/"
    logger = Logger("rf_survey", log_path, "stream-"+log_time+".log")
    grace = GracefulKiller()
    with open(os.environ["HOME"]+"/rf_survey.pid","w") as f:
        f.write(str(os.getpid()))
    logger.write_log("DEBUG", "PID: %s"%(os.getpid()))
    if os.path.exists("/home/pi/nohup.out"):
        os.remove("/home/pi/nohup.out")
    cpr = Restoration()

    # Parser to parse the parameter inputs
    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required named arguments')
    required.add_argument('-f1', '--frequency_start', type=lambda x: int(float(x)), help='Start Center Frequency in e6 Hz', required=True)
    parser.add_argument('-f2', '--frequency_end', type=lambda x: int(float(x)), help='End Center Frequency in e6 Hz')

    required.add_argument('-b', '--bandwidth', type=lambda x: int(float(x)), help='Bandwidth in e6 Hz', required=True)
    required.add_argument('-s', '--samples', type=lambda x: int(float(x)), help='Total number of sample', required=True)
    required.add_argument('-g', '--gain', type=gain_check, help='Receive gain in dB (0-76)', required=True)
    required.add_argument('-r', '--records', type=int, help='# of files generated per frequency', required=True)
    required.add_argument('-o', '--organization', type=str, help='Location Identifier', required=True)
    required.add_argument('-gcs', '--coordinates', type=str, help='Coordinates in 40.0149N105.2705W format', required=True)
    parser.add_argument('-c','--cycles', type=int, help='# of times all frequencies are swept')
    required.add_argument('-t', '--timer', type=float, help='time interval in seconds - min = BW/1e6*0.2', required=True)
    parser.add_argument('-m', '--maxtimer', type=int, help='max random time interval in seconds - min = BW/1e6*0.2')
    parser.add_argument('-d', '--delay', type=float, help='execute the script [x] seconds in the future')
    parser.add_argument('-rs', '--seed', type=int, help='only used when activating multiple devices through the GUI')
    args = parser.parse_args()

    if args.delay == None:
        args.delay = 0

    group = group_number()
    start = 0

    if args.timer == 0:
        if args.seed != None:
            random.seed(args.seed)
        if args.maxtimer < args.bandwidth/1e6*0.2:
            logger.write_log("DEBUG", "Time interval needs to be at least BW/1e6*0.2")
            parser.error("Time interval needs to be at least BW/1e6*0.2")
            cleanup()
            return # if a max random timer interval is not given, the default is set to 60 seconds
        if args.maxtimer == None:
            logger.write_log("DEBUG", "-m is required when -t is set to 0")
            parser.error("-m is required when -t is set to 0")
            cleanup()
            return
    if args.cycles == None:
        args.cycles = 1

    length = args.samples/args.bandwidth
    start_frequency = args.frequency_start
    if not args.frequency_end:
        args.frequency_end = start_frequency

    hostname= str(subprocess.check_output(['hostname']))[2:-3]

    dict = {}
    # If the provided gain value is 0, determines the optimal gain value
    if args.gain == 0:
        if not grace.kill_now:
            stream = Streamer(args.samples, args.frequency_start, args.bandwidth, args.gain, args.timer, length, hostname, args.organization, args.coordinates)
            stream.setup_stream()
            stream.start_stream()

            # This value needs to be changed for different USRPs - B200 series has a gain range from 0-76
            levels = np.arange(76, -1, -1)

            for i in range (len(levels)):
                if not grace.kill_now:
                    dict[levels[i]] = stream.receive_gain(levels[i])
                    # This value needs to be adjusted with different CPU format settings - for sc16 15000 uses only 14 of the available 15 bits
                    if (dict[levels[i]][0] < 15000 and dict[levels[i]][1] <15000) and (dict[levels[i]][2] == 0 and dict[levels[i]][3] == 0):
                        args.gain = levels[i]
                        print(args.gain)
                        stream.stop_stream()
                        break
                    time.sleep(10)

    # Starts the data collection streamer (not the data collection itself)
    stream = Streamer(args.samples, args.frequency_start, args.bandwidth, args.gain, args.timer, length, hostname, args.organization, args.coordinates, group)

    stream.setup_stream()
    stream.start_stream()

    logger.write_log("INFO","Checking Pulse.")
    pulse = cpr.check_pulse()
    cronjob = Cronify()

    if pulse == 1:
        start_frequency, args.cycles, group, start, start_time = cpr.cardioversion()
        logger.write_log("INFO","Pulse found: restoration frequency = {}, cycles left = {}, original start time was {}.".format(
            start_frequency, args.cycles, start_time
        ))
    elif pulse == 2:
        logger.write_log("WARNING","Survey has already ended. Shutting down and removing lifesign and cron job.")
        os.remove(os.environ["HOME"]+"/lifesigns.json")
        os.remove(os.environ["HOME"]+"/rf_survey.pid")
        cronjob.delete_job()
        sys.exit()
    else:
        logger.write_log("INFO","No Pulse, moving on.")

    configs = {
        "organization" : args.organization,
        "gcs" : args.coordinates,
        "start_frequency" : args.frequency_start,
        "end_frequency" : args.frequency_end,
        "sampling_rate" : args.bandwidth,
        "interval" : int(args.timer),
        "samples" : args.samples,
        "cycles" : args.cycles,
        "recordings" : args.records,
        "gain" : args.gain,
        "group" : group,
        "start_time" : str(datetime.now()),
        "delay" : args.delay
    }

    if pulse == 1:
        configs["start_time"] = start_time
        actual_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f") + relativedelta(seconds=+args.delay)
        logger.write_log("INFO","Approximate scheduled start time was: {}.".format(actual_start))
        if actual_start > datetime.now():
            new_delay = (actual_start - datetime.now()).total_seconds()
            logger.write_log("INFO","Remaining delay: {}.".format(new_delay))
            sleep(new_delay, grace)
    else:
        try:
            with open(os.environ["HOME"]+"/lifesigns.json","w") as outfile:
                json.dump(configs, outfile)
            cronjob.create_job(configs)
            logger.write_log("WARNING","Restoration File and Cronjob created.")
            logger.write_log("INFO", "Restoration File created with Start Time: {}, Delay: {}, Start Frequency: {}, End Frequency: {}, Sampling Rate: {}, Interval: {}, Samples: {}, Cycles: {}, Recordings: {}, Gain: {}, Group: {}, Organization: {}, Coordinates: {}".format(
                configs["start_time"], configs["delay"], configs["start_frequency"], configs["end_frequency"], configs["sampling_rate"], configs["interval"], configs["samples"], configs["cycles"], configs["recordings"], configs["gain"], configs["group"], configs["organization"], configs["gcs"]
            ))
        except Exception as e:
            logger.write_log("ERROR","Creating Restoration File and Cronjob failed with: %s."%(repr(e)))
        if args.delay != 0:
            sleep(args.delay, grace)

    if args.cycles == 0:
        try:
            while not grace.kill_now:
                while start_frequency <= args.frequency_end and not grace.kill_now:
                    logger.write_log("INFO","Frequency step: %s"%(start_frequency/1e6))
                    # The -r [records] argument determines how many IQ data files of size [samples] * 4 Bytes are created in [timer] intervals
                    for j in range(int(start), args.records):
                        if args.timer == 0 and not grace.kill_now:
                            stream.rand_timer(args.maxtimer)
                        else:
                            stream.timer(args.timer)

                        # Starts the collection of IQ data samples
                        start_time=time.time()
                        stream.receive_samples(start_frequency)
                        end_time=time.time()
                        logger.write_log("INFO","Processing time: %s"%(end_time-start_time))
                        if grace.kill_now:
                            break
                    start = 0
                    start_frequency = start_frequency + args.bandwidth
                start_frequency = args.frequency_start
        except(TypeError) as e:
            print("An end center frequency needs to be provided\n%s" % (repr(e)))
            logger.write_log("DEBUG","An end center frequency needs to be provided %s" % (repr(e)))
            cleanup()
            return
    else:
        for i in range(args.cycles):
            if not grace.kill_now:
                try:
                    while start_frequency <= args.frequency_end and not grace.kill_now:
                        logger.write_log("INFO","Frequency step: %s"%(start_frequency/1e6))
                        # The -r [records] argument determines how many IQ data files of size [samples] * 4 Bytes are created in [timer] intervals
                        for j in range(start, args.records):
                            if not grace.kill_now:
                                if args.timer == 0:
                                    stream.rand_timer(args.maxtimer)
                                else:
                                    stream.timer(args.timer)

                                # Starts the collection of IQ data samples
                                start_time=time.time()
                                stream.receive_samples(start_frequency)
                                end_time=time.time()
                                logger.write_log("INFO","Processing time: %s"%(end_time-start_time))
                            else:
                                break
                        start = 0
                        start_frequency = start_frequency + args.bandwidth
                    start_frequency = args.frequency_start
                except(TypeError) as e:
                    print("An end center frequency needs to be provided\n%s" % (repr(e)))
                    logger.write_log("DEBUG","An end center frequency needs to be provided %s" % (repr(e)))
                    cleanup()
                    return
            else:
                break

    # Stops the stream and closes the connection to the SDR
    stream.stop_stream()
    os.remove(os.environ["HOME"]+"/rf_survey.pid")

    """the if clause below is only for testing"""

    #if not grace.kill_now:
    try:
        cronjob.delete_job()
        os.remove(os.environ["HOME"]+"/lifesigns.json")
        logger.write_log("WARNING","Restoration File and Cronjob deleted.")
    except Exception as e:
        logger.write_log("ERROR","Deleting Restoration File and Cronjob failed with: %s."%(repr(e)))


if __name__ == '__main__':
    pid_path = os.environ["HOME"]+"/rf_survey.pid"
    if os.path.exists(pid_path):
        with open(os.environ["HOME"]+"/rf_survey.pid","r") as f:
            pid = f.readlines()
        if os.path.exists("/proc/"+pid[0]):
            sys.exit("Survey already running! Interrupt running survey first.")
    main()
