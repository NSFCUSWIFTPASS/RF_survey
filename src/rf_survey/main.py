# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import asyncio
import time
import sys
import signal
import socket
import uuid
from tendo import singleton

from rf_shared.nats_client import NatsProducer
from rf_shared.logger import Logger

from rf_survey.mock_streamer import Streamer
from rf_survey.cli import parse_args
from rf_survey.config import settings


async def run(args):
    main_logger = Logger(name="rf_survey", log_level=settings.LOG_LEVEL)
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal():
        if not shutdown_event.is_set():
            main_logger.info("Shutdown signal received. Signalling tasks to stop.")
            shutdown_event.set()

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
        output_path=settings.STORAGE_PATH,
        logger=Logger(name="streamer", log_level=settings.LOG_LEVEL),
    )

    subject = f"jobs.rf.{hostname}"

    producer = NatsProducer(
        logger=Logger(name="nats_producer", log_level=settings.LOG_LEVEL),
        subject=subject,
        connect_options={
            "servers": settings.NATS_URL,
            "token": settings.NATS_TOKEN.get_secret_value()
            if settings.NATS_TOKEN
            else None,
        },
    )

    # comment out for now, review methods for restart on pi reboot
    # cronjob = Cronify()

    async def sweep():
        await perform_frequency_sweep(
            stream,
            main_logger,
            shutdown_event,
            args.frequency_start,
            args.frequency_end,
            args.bandwidth,
            args.records,
            producer,
        )

    try:
        stream.initialize()
        stream.start_stream()
        await producer.connect()

        # setup signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)

        if args.cycles == 0:
            while not shutdown_event.is_set():
                await sweep()
        else:
            for _ in range(args.cycles):
                if shutdown_event.is_set():
                    break
                await sweep()

    except Exception as e:
        main_logger.error(f"Critical error: {e}")

    finally:
        main_logger.info("Cleaning up resources... stopping stream.")
        stream.stop_stream()
        await producer.close()


async def perform_frequency_sweep(
    stream: Streamer,
    logger: Logger,
    shutdown_event: asyncio.Event,
    frequency_start: int,
    frequency_end: int,
    bandwidth: int,
    records: int,
    producer: NatsProducer,
):
    """
    Performs a single sweep across the specified frequency range.
    """
    center_frequency_hz = frequency_start
    while center_frequency_hz <= frequency_end and not shutdown_event.is_set():
        for _ in range(records):
            # this sleep is interruptible from a signal
            await stream.wait_for_next_collection(shutdown_event)

            # check if we were interrupted if so break
            if shutdown_event.is_set():
                break

            start_time = time.time()
            metadata_record = stream.receive_samples(center_frequency_hz)
            end_time = time.time()

            logger.info(
                f"Frequency step: {center_frequency_hz} Processing time: {end_time - start_time}"
            )

            await producer.publish_metadata(metadata_record)

        center_frequency_hz += bandwidth


def main():
    try:
        _ = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit("Survey already running! Another process holds the lock file.")

    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
