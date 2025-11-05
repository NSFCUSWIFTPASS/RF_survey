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
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                logger.error("OK OK OK OK OK OK")

    def on_open(self, ws: ClientConnection):
        pass

    async def on_event(self, ws: ClientConnection, evt: Event, message: bytes | str):
        pass
