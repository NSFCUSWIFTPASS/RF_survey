import asyncio
import json
from typing import Optional

from zmsclient.zmc.client_asyncio import ZmsZmcClientAsyncio
from zmsclient.zmc.v1.models import Error, AnyObject
from rf_shared.logger import Logger

from rf_survey.monitor import (
    IZmsMonitor,
    ZmsMonitor,
)
from rf_survey.config import AppSettings
from rf_survey.types import ReconfigurationCallback


class ZmsInitializationError(Exception):
    """Raised when a fatal error occurs during ZMS component setup."""

    pass


async def register_monitor_schema(
    zmc_client: ZmsZmcClientAsyncio, monitor_id: str, monitor_schema: dict
) -> None:
    """Defines and registers the monitor's parameter schema with ZMS."""

    try:
        response = await zmc_client.get_monitor(monitor_id=monitor_id)
        monitor = response.parsed
        if isinstance(monitor, Error):
            raise ZmsInitializationError(f"Unable to fetch monitor {monitor.error}")

        monitor.parameter_defs = AnyObject.from_dict(src_dict=monitor_schema)
        await zmc_client.update_monitor(monitor_id=monitor_id, body=monitor)

    except Exception as e:
        raise ZmsInitializationError(
            f"Failed to register monitor schema for monitor ID {monitor_id}. "
        ) from e


async def initialize_zms_monitor(
    settings: AppSettings,
    reconfiguration_callback: ReconfigurationCallback,
    shutdown_event: asyncio.Event,
) -> Optional[IZmsMonitor]:
    """
    This factory contains all ZMS-specific setup logic.
    """
    if settings.zms:
        zmc_client = ZmsZmcClientAsyncio(
            settings.zms.zmc_http,
            settings.zms.token.get_secret_value(),
            raise_on_unexpected_status=True,
        )

        with open(settings.zms.monitor_schema_path, "r") as f:
            monitor_schema = json.load(f)

        # Register our configurable parameters
        await register_monitor_schema(
            zmc_client, settings.zms.monitor_id, monitor_schema
        )

        return ZmsMonitor(
            monitor_id=settings.zms.monitor_id,
            reconfiguration_callback=reconfiguration_callback,
            zmc_client=zmc_client,
            shutdown_event=shutdown_event,
            logger=Logger("heartbeat", settings.LOG_LEVEL),
        )

    return None
