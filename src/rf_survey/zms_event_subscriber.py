import json
import logging
import asyncio
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from zmsclient.zmc.v1.models import Subscription, Event, Error
from zmsclient.zmc.client_asyncio import ZmsZmcClientAsyncio


class ZmsEventSubscriber:
    def __init__(
        self,
        zmsclient: ZmsZmcClientAsyncio,
        subscription: Subscription,
        reconnect_on_error: bool = False,
    ):
        self.zmsclient = zmsclient
        self.subscription = subscription
        self.reconnect_on_error = reconnect_on_error

    def _parse_event(self, msg):
        return Event.from_dict(src_dict=json.loads(msg))

    def _build_ws_url(self, id: str):
        ws_url = self.zmsclient._base_url + "/subscriptions/" + id + "/events"
        ws_url = ws_url.replace("http", "ws")

        return ws_url

    async def run_async(self):
        logger = logging.getLogger(__name__).getChild("AsyncZmsSubscription")

        while True:
            subscription_id = None
            try:
                logger.info(f"{self.subscription}")
                response = await self.zmsclient.create_subscription(
                    body=self.subscription
                )
                subscription_result = response.parsed
                if isinstance(subscription_result, Error):
                    logger.error(
                        f"Failed to create subscription: {subscription_result.error}. Retrying..."
                    )
                    await asyncio.sleep(10)
                    continue

                subscription_id = subscription_result.id
                logger.debug(f"Created subscription with id: {subscription_id}")

                ws_url = self._build_ws_url(subscription_id)
                headers = {"X-Api-Token": self.zmsclient.token}

                async with websockets.connect(ws_url, additional_headers=headers) as ws:
                    self.on_open(ws)
                    async for message in ws:
                        await self.on_event(ws, self._parse_event(message), message)

            except asyncio.CancelledError:
                logger.info("Subscription task cancelled. Shutting down.")
                break

            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
                logger.warning(f"WS connection failed: {e}. Preparing to reconnect.")

            except Exception as e:
                logger.error(f"A critical error occurred: {e}", exc_info=True)

            finally:
                if subscription_id:
                    logger.info(f"Cleaning up subscription {subscription_id}.")
                    try:
                        await self.zmsclient.delete_subscription(
                            subscription_id=subscription_id
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to delete subscription {subscription_id}: {e}"
                        )

            if self.reconnect_on_error:
                logger.info("Attempting to reconnect in 10 seconds...")
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    logger.info("Reconnect wait cancelled. Shutting down.")
                    break
            else:
                logger.info("Reconnect is disabled. Exiting loop.")
                break

    def on_open(self, ws: ClientConnection):
        pass

    async def on_event(self, ws: ClientConnection, evt: Event, message: bytes | str):
        pass
