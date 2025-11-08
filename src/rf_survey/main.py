import asyncio
import sys
from pathlib import Path
from tendo import singleton
import signal

from rf_shared.logger import Logger
from rf_shared.nats_client import NatsProducer

from rf_survey.app import SurveyApp
from rf_survey.config import app_settings
from rf_survey.cli import update_settings_from_args
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

    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    def signal_handler():
        print("\nShutdown signal received. Cancelling all tasks...")
        if main_task and not main_task.done():
            main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    settings = update_settings_from_args(app_settings)

    app_info = ApplicationInfo(
        hostname=settings.HOSTNAME,
        organization=settings.ORGANIZATION,
        coordinates=settings.COORDINATES,
        output_path=Path(settings.STORAGE_PATH),
    )

    sweep_config = SweepConfig(
        start_hz=settings.FREQUENCY_START,
        end_hz=settings.FREQUENCY_END,
        step_hz=settings.BANDWIDTH,
        cycles=settings.CYCLES,
        records_per_step=settings.RECORDS,
        interval_sec=settings.TIMER,
        max_jitter_sec=settings.JITTER,
    )

    receiver_config = ReceiverConfig(
        bandwidth_hz=settings.BANDWIDTH,
        gain_db=settings.GAIN,
        duration_sec=settings.DURATION_SEC,
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

    watchdog = ApplicationWatchdog(
        timeout_seconds=30,
        logger=Logger("watchdog", settings.LOG_LEVEL),
    )

    app = SurveyApp(
        app_info=app_info,
        sweep_config=sweep_config,
        receiver=receiver,
        producer=producer,
        watchdog=watchdog,
        zms_monitor=NullZmsMonitor(),
        logger=Logger("rf_survey", settings.LOG_LEVEL),
    )

    # If ZMS configuration is not provided
    # returns None
    zms_monitor = await initialize_zms_monitor(
        settings=settings,
        reconfiguration_callback=app.apply_zms_reconfiguration,
    )

    ## Check if we have Zms monitor enabled
    if zms_monitor:
        app.zms_monitor = zms_monitor

    # If Zms is not managing us signal the survey to start
    # starts paused by default, ZMS will tell us to start
    if not isinstance(zms_monitor, ZmsMonitor):
        await app.start_survey()

    await app.run()


def main():
    try:
        asyncio.run(run())
    except asyncio.CancelledError:
        print("rf-survey shut down successfully.")


if __name__ == "__main__":
    main()
