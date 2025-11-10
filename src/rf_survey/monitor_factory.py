import asyncio
import json
from typing import Optional

from zmsclient.zmc.client_asyncio import ZmsZmcClientAsyncio
from zmsclient.identity.client_asyncio import ZmsIdentityClientAsyncio
from zmsclient.zmc.v1.models import Error as ZmcError, Monitor, AnyObject
from zmsclient.identity.v1.models import error as IdentityError, Token

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
) -> str:
    """Defines and registers the monitor's parameter schema with ZMS."""

    try:
        response = await zmc_client.get_monitor(monitor_id=monitor_id)
        monitor = response.parsed
        if not isinstance(monitor, Monitor):
            error_msg = monitor.error if isinstance(monitor, ZmcError) else "Unknown"
            raise ZmsInitializationError(f"Unable to fetch monitor: {error_msg}")

        element_id = monitor.element_id
        if not element_id:
            raise ZmsInitializationError(
                "Fetched monitor object did not contain an element_id."
            )

        monitor.parameter_defs = AnyObject.from_dict(src_dict=monitor_schema)
        await zmc_client.update_monitor(monitor_id=monitor_id, body=monitor)

    except Exception as e:
        raise ZmsInitializationError(
            f"Failed to register monitor schema for monitor ID {monitor_id}. "
        ) from e

    return element_id


async def initialize_zms_monitor(
    settings: AppSettings,
    reconfiguration_callback: ReconfigurationCallback,
) -> Optional[IZmsMonitor]:
    """
    This factory contains all ZMS-specific setup logic.
    """
    if settings.zms:
        token_secret = settings.zms.token.get_secret_value()

        zmc_client = ZmsZmcClientAsyncio(
            settings.zms.zmc_http,
            token_secret,
            raise_on_unexpected_status=True,
        )

        identity_client = ZmsIdentityClientAsyncio(
            settings.zms.identity_http,
            token_secret,
            raise_on_unexpected_status=True,
        )

        with open(settings.zms.monitor_schema_path, "r") as f:
            monitor_schema = json.load(f)

        # Register our configurable parameters and get element_id
        element_id = await register_monitor_schema(
            zmc_client, settings.zms.monitor_id, monitor_schema
        )

        # Get our user ID
        response = await identity_client.get_token_this()
        token_info = response.parsed

        if not isinstance(token_info, Token):
            error_msg = (
                token_info.error if isinstance(token_info, IdentityError) else "Unknown"
            )
            raise ZmsInitializationError(
                f"Failed to get token info from identity service: {error_msg}"
            )

        return ZmsMonitor(
            monitor_id=settings.zms.monitor_id,
            element_id=element_id,
            user_id=token_info.user_id,
            zmc_client=zmc_client,
            reconfiguration_callback=reconfiguration_callback,
        )

    return None
