import asyncio
from aiohttp import web
from prometheus_client.aiohttp import make_aiohttp_handler
from prometheus_client import CollectorRegistry

class Metrics:
    def __init__(self, listen_port: int = 9090):
        self._registry = CollectorRegistry()
        self._listen_port = listen_port

    async def run(self):
        app = web.Application()
        handler = make_aiohttp_handler(registry=self._registry)

        app.router.add_get("/metrics", handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self._listen_port)
        
        try:
            await site.start()
            print(f"Metrics server started on port {self._listen_port}")
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
            print("Metrics server shut down.")
