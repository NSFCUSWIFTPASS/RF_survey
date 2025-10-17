# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import asyncio
import sys
from tendo import singleton

from rf_shared.logger import Logger
from rf_shared.nats_client import NatsProducer

from rf_survey.app import SurveyApp
from rf_survey.mock_streamer import Streamer
from rf_survey.config import settings
from rf_survey.cli import parse_args


def main():
    """
    Main application entry point.
    """
    try:
        _ = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit("Survey already running! Another process holds the lock file.")

    args = parse_args()

    streamer = Streamer(
        num_samples=args.samples,
        bandwidth_hz=args.bandwidth,
        gain_db=args.gain,
        interval_secs=args.timer,
        max_jitter_secs=args.jitter,
        hostname=settings.HOSTNAME,
        organization=args.organization,
        coordinates=args.coordinates,
        output_path=settings.STORAGE_PATH,
        logger=Logger(name="streamer", log_level=settings.LOG_LEVEL),
    )

    producer = NatsProducer(
        subject=settings.NATS_SUBJECT,
        connect_options={
            "servers": settings.NATS_URL,
            "token": settings.NATS_TOKEN.get_secret_value()
            if settings.NATS_TOKEN
            else None,
        },
        logger=Logger(name="nats_producer", log_level=settings.LOG_LEVEL),
    )

    app = SurveyApp(
        args=args,
        streamer=streamer,
        producer=producer,
        logger=Logger("rf_survey", settings.LOG_LEVEL),
    )

    asyncio.run(app.run())


if __name__ == "__main__":
    main()
