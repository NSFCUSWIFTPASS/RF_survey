# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import time
import os
import argparse
import sys
import random
from datetime import datetime
import socket

from rf_survey.mock_streamer import Streamer
from rf_survey.utils.logger import Logger
from rf_survey.utils.graceful_killer import GracefulKiller
# from Cronify import Cronify

from config import parse_args

#####################################################
# The streamer class contains all functions related #
# to running the I/Q data collection stream.        #
#####################################################


def group_number(length=6):
    group = ""
    for i in range(length):
        random_integer = random.randint(97, 97 + 26 - 1)
        flip_bit = random.randint(0, 1)
        random_integer = random_integer - 32 if flip_bit == 1 else random_integer
        group += chr(random_integer)
    return group


def sleep(seconds, grace):
    now = time.monotonic()
    end = now + seconds
    for i in range(int(seconds)):
        if grace.kill_now:
            sys.exit(0)
        elif time.monotonic() + 1 <= end:
            time.sleep(1)
        else:
            time.sleep(end - time.monotonic())
            break


def cleanup():
    if os.path.exists(os.environ["HOME"] + "/rf_survey.pid"):
        os.remove(os.environ["HOME"] + "/rf_survey.pid")
    cronjob = Cronify()
    cronjob.delete_job()


def run():
    log_time = datetime.now().strftime("%Y-%m-%d")
    log_path = os.environ["HOME"] + "/logs/"
    logger = Logger("rf_survey", log_path, "stream-" + log_time + ".log")
    grace = GracefulKiller()

    with open(os.environ["HOME"] + "/rf_survey.pid", "w") as f:
        f.write(str(os.getpid()))
    logger.write_log("DEBUG", "PID: %s" % (os.getpid()))
    if os.path.exists("/home/pi/nohup.out"):
        os.remove("/home/pi/nohup.out")

    group = group_number()
    args = parse_args()

    length = args.samples / args.bandwidth
    hostname = socket.gethostname()

    # Starts the data collection streamer (not the data collection itself)
    stream = Streamer(
        args.samples,
        args.frequency_start,
        args.bandwidth,
        args.gain,
        args.timer,
        args.jitter,
        length,
        hostname,
        args.organization,
        args.coordinates,
        group,
    )

    stream.setup_stream()
    stream.start_stream()

    # comment out for now, review methods for restart on pi reboot
    # cronjob = Cronify()

    # THIS WILL BE THE METADATA
    # configs = {
    #    "organization": args.organization,
    #    "gcs": args.coordinates,
    #    "start_frequency": args.frequency_start,
    #    "end_frequency": args.frequency_end,
    #    "sampling_rate": args.bandwidth,
    #    "interval": int(args.timer),
    #    "samples": args.samples,
    #    "cycles": args.cycles,
    #    "recordings": args.records,
    #    "gain": args.gain,
    #    "group": group,
    #    "start_time": str(datetime.now()),
    #    "delay": args.delay,
    # }

    if args.cycles == 0:
        while not grace.kill_now:
            perform_frequency_sweep(stream, logger, grace, args)
    else:
        for _ in range(args.cycles):
            if grace.kill_now:
                break
            perform_frequency_sweep(stream, logger, grace, args)

    # Stops the stream and closes the connection to the SDR
    stream.stop_stream()
    os.remove(os.environ["HOME"] + "/rf_survey.pid")


def perform_frequency_sweep(stream, logger, grace, args):
    """
    Performs a single sweep across the specified frequency range.
    """
    start_frequency = args.frequency_start
    try:
        while start_frequency <= args.frequency_end and not grace.kill_now:
            logger.write_log("INFO", "Frequency step: %s" % (start_frequency / 1e6))
            # The -r [records] argument determines how many IQ data files are created
            for _ in range(args.records):
                if grace.kill_now:
                    break

                stream.wait_for_next_collection()

                # Starts the collection of IQ data samples
                start_time = time.time()
                stream.receive_samples(start_frequency)
                end_time = time.time()
                logger.write_log(
                    "INFO", "Processing time: %s" % (end_time - start_time)
                )

            start_frequency = start_frequency + args.bandwidth
    except TypeError:
        logger.write_log("DEBUG", "An end center frequency needs to be provided.")
        raise


def main():
    pid_path = os.environ["HOME"] + "/rf_survey.pid"
    if os.path.exists(pid_path):
        with open(os.environ["HOME"] + "/rf_survey.pid", "r") as f:
            pid = f.readlines()
        if os.path.exists("/proc/" + pid[0]):
            sys.exit("Survey already running! Interrupt running survey first.")
    run()


if __name__ == "__main__":
    main()
