# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import time
import threading
import sys
import signal
import socket
import uuid
from tendo import singleton

from rf_survey.mock_streamer import Streamer

# from rf_survey.streamer import Streamer
from rf_survey.utils.logger import Logger
from rf_survey.config import parse_args
# from Cronify import Cronify


# def cleanup():
#    cronjob = Cronify()


def run(args):
    main_logger = Logger("rf_survey")
    streamer_logger = Logger("streamer")
    shutdown_event = threading.Event()

    def signal_handler(signum, frame):
        if not shutdown_event.is_set():
            main_logger.write_log(
                "INFO", "Shutdown signal received. Signalling tasks to stop."
            )
            shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    hostname = socket.gethostname()
    group_id = str(uuid.uuid4())

    stream = Streamer(
        num_samples=args.samples,
        bandwidth_hz=args.bandwidth,
        gain_db=args.gain,
        interval_secs=args.timer,
        max_jitter_secs=args.jitter,
        hostname=hostname,
        organization=args.organization,
        coordinates=args.coordinates,
        group_id=group_id,
        output_path="/mnt/net-sync/",
        logger=streamer_logger,
    )

    stream.initialize()
    stream.start_stream()

    # comment out for now, review methods for restart on pi reboot
    # cronjob = Cronify()

    def sweep():
        perform_frequency_sweep(
            stream,
            main_logger,
            shutdown_event,
            args.frequency_start,
            args.frequency_end,
            args.bandwidth,
            args.records,
        )

    try:
        if args.cycles == 0:
            while not shutdown_event.is_set():
                sweep()
        else:
            for _ in range(args.cycles):
                if shutdown_event.is_set():
                    break
                sweep()
    except Exception as e:
        main_logger.write_log(
            "ERROR",
            f"Critical error: {e}",
        )

    finally:
        main_logger.write_log("INFO", "Cleaning up resources... stopping stream.")
        stream.stop_stream()


def perform_frequency_sweep(
    stream: Streamer,
    logger: Logger,
    shutdown_event,
    frequency_start: int,
    frequency_end: int,
    bandwidth: int,
    records: int,
):
    """
    Performs a single sweep across the specified frequency range.
    """
    center_frequency_hz = frequency_start
    while center_frequency_hz <= frequency_end and not shutdown_event.is_set():
        for _ in range(records):
            # this sleep is interruptible from a signal
            stream.wait_for_next_collection(shutdown_event)

            # check if we were interrupted if so break
            if shutdown_event.is_set():
                break

            start_time = time.time()
            stream.receive_samples(center_frequency_hz)
            end_time = time.time()
            logger.write_log(
                "INFO",
                f"Frequency step: {center_frequency_hz} Processing time: {end_time - start_time}",
            )

        center_frequency_hz += bandwidth


def main():
    try:
        _ = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit("Survey already running! Another process holds the lock file.")

    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
