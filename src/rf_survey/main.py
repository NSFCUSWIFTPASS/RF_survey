# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import asyncio
import sys
from pathlib import Path
from tendo import singleton

from rf_shared.logger import Logger
from rf_shared.nats_client import NatsProducer

from rf_survey.app import SurveyApp
from rf_survey.config import settings
from rf_survey.cli import parse_args
from rf_survey.receiver import Receiver
from rf_survey.models import ApplicationInfo, SweepConfig, ReceiverConfig
from rf_survey.watchdog import ApplicationWatchdog
from rf_survey.monitor import ZmsMonitor, NullZmsMonitor
from rf_survey.monitor_factory import initialize_zms_monitor


async def run():
    """
    Main application entry point.
    """
    try:
        _ = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit("Survey already running! Another process holds the lock file.")

    args = parse_args()

    shutdown_event = asyncio.Event()

    app_info = ApplicationInfo(
        hostname=settings.HOSTNAME,
        organization=args.organization,
        coordinates=args.coordinates,
        output_path=Path(settings.STORAGE_PATH),
    )

    sweep_config = SweepConfig(
        start_hz=args.frequency_start,
        end_hz=args.frequency_end,
        cycles=args.cycles,
        records_per_step=args.records,
        interval_sec=args.timer,
        max_jitter_sec=args.jitter,
    )

    receiver_config = ReceiverConfig(
        bandwidth_hz=args.bandwidth,
        gain_db=args.gain,
        duration_sec=args.duration_sec,
    )

    receiver = Receiver(
        receiver_config=receiver_config,
        logger=Logger(name="receiver", log_level=settings.LOG_LEVEL),
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

    watchdog_timeout = args.timer + 10  # interval between samples + buffer
    watchdog = ApplicationWatchdog(
        timeout_seconds=watchdog_timeout,
        shutdown_event=shutdown_event,
        logger=Logger("watchdog", settings.LOG_LEVEL),
    )

    app = SurveyApp(
        app_info=app_info,
        sweep_config=sweep_config,
        shutdown_event=shutdown_event,
        receiver=receiver,
        producer=producer,
        watchdog=watchdog,
        zms_monitor=NullZmsMonitor(shutdown_event=shutdown_event),
        logger=Logger("rf_survey", settings.LOG_LEVEL),
    )

    # If ZMS configuration is not provided
    # returns None
    zms_monitor = await initialize_zms_monitor(
        settings=settings,
        reconfiguration_callback=app.apply_zms_reconfiguration,
        shutdown_event=shutdown_event,
    )

    # Check if we have Zms monitor enabled
    if zms_monitor:
        app.zms_monitor = zms_monitor

    # If Zms is managing us do not start the survey until we receive
    # an active state command, we could be initializing into a paused state
    if isinstance(zms_monitor, ZmsMonitor):
        await app.pause_survey()

    await app.run()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
