# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import time
import os
import sys
import random
import socket
from tendo import singleton

from rf_survey.mock_streamer import Streamer

# from rf_survey.streamer import Streamer
from rf_survey.utils.logger import Logger
from rf_survey.utils.graceful_killer import GracefulKiller
from rf_survey.config import parse_args
# from Cronify import Cronify


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


# def cleanup():
#    cronjob = Cronify()


def run():
    main_logger = Logger("rf_survey")
    streamer_logger = Logger("streamer")
    grace = GracefulKiller()

    group = group_number()
    args = parse_args()

    hostname = socket.gethostname()

    # Starts the data collection streamer (not the data collection itself)
    stream = Streamer(
        num_samples=args.samples,
        bandwidth_hz=args.bandwidth,
        gain_db=args.gain,
        interval_secs=args.timer,
        max_jitter_secs=args.jitter,
        hostname=hostname,
        organization=args.organization,
        coordinates=args.coordinates,
        group_id=group,
        output_path="/mnt/net-sync/",
        logger=streamer_logger,
    )

    stream.initialize()
    stream.start_stream()

    # comment out for now, review methods for restart on pi reboot
    # cronjob = Cronify()

    if args.cycles == 0:
        while not grace.kill_now:
            perform_frequency_sweep(stream, main_logger, grace, args)
    else:
        for _ in range(args.cycles):
            if grace.kill_now:
                break
            perform_frequency_sweep(stream, main_logger, grace, args)

    # Stops the stream and closes the connection to the SDR
    stream.stop_stream()


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
    try:
        _ = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit("Survey already running! Another process holds the lock file.")

    run()


if __name__ == "__main__":
    main()
