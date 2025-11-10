import asyncio
import logging
from aiohttp import web
from prometheus_client.aiohttp import make_aiohttp_handler
from prometheus_client import CollectorRegistry, Gauge

from rf_survey.models import ApplicationInfo, SweepConfig, ReceiverConfig

logger = logging.getLogger(__name__)


class Metrics:
    def __init__(self, app_info: ApplicationInfo, listen_port: int = 9090):
        self.registry = CollectorRegistry()
        self._listen_port = listen_port

        self.build_info = Gauge(
            "rf_survey_build_info",
            "Hot and version information for the application",
            ["version", "hostname"],
            registry=self.registry,
        )
        self.build_info.labels(
            version=app_info.version, hostname=app_info.hostname
        ).set(1)

        # USRP Temp
        self.usrp_temperature = Gauge(
            "rf_survey_sdr_temperature_celsius",
            "Current temperature of the SDR hardware in Celsius",
            registry=self.registry,
        )

        # Processing queue
        self.processing_queue_size = Gauge(
            "rf_survey_processing_queue_size",
            "Number of items in the processing queue",
            registry=self.registry,
        )

        # Sweep Config
        self.config_start_hz = Gauge(
            "rf_survey_config_start_hz",
            "Current start frequency of the sweep in Hz",
            registry=self.registry,
        )
        self.config_end_hz = Gauge(
            "rf_survey_config_end_hz",
            "Current end frequency of the sweep in Hz",
            registry=self.registry,
        )
        self.config_interval_sec = Gauge(
            "rf_survey_config_interval_sec",
            "Current interval between captures in seconds",
            registry=self.registry,
        )
        self.config_step_hz = Gauge(
            "rf_survey_config_step_hz",
            "Current step frequency of the sweep in Hz",
            registry=self.registry,
        )
        self.config_cycles = Gauge(
            "rf_survey_config_cycles",
            "Configured number of sweep cycles to run (0 for infinite)",
            registry=self.registry,
        )
        self.config_records_per_step = Gauge(
            "rf_survey_config_records_per_step",
            "Number of records to capture at each frequency step",
            registry=self.registry,
        )
        self.config_max_jitter_sec = Gauge(
            "rf_survey_config_max_jitter_sec",
            "Maximum random delay to add before a capture in seconds",
            registry=self.registry,
        )

        # Receiver Config
        self.receiver_config_gain_db = Gauge(
            "rf_surveyor_receiver_config_gain_db",
            "Current receiver gain in dB",
            registry=self.registry,
        )
        self.receiver_config_bandwidth_hz = Gauge(
            "rf_surveyor_receiver_config_bandwidth_hz",
            "Current receiver bandwidth in Hz",
            registry=self.registry,
        )
        self.receiver_config_duration_sec = Gauge(
            "rf_surveyor_receiver_config_duration_sec",
            "Current capture duration in seconds",
            registry=self.registry,
        )

    def update_temperature(self, temp_c: float):
        """Updates the temperature gauge."""
        self.usrp_temperature.set(temp_c)

    def update_queue_size(self, size: int):
        """Updates the processing queue size gauge."""
        self.processing_queue_size.set(size)

    def update_sweep_config(self, sweep_config: SweepConfig):
        """
        Updates all gauges related to the sweep configuration.
        """
        self.config_start_hz.set(sweep_config.start_hz)
        self.config_end_hz.set(sweep_config.end_hz)
        self.config_step_hz.set(sweep_config.step_hz)
        self.config_cycles.set(sweep_config.cycles)
        self.config_records_per_step.set(sweep_config.records_per_step)
        self.config_interval_sec.set(sweep_config.interval_sec)
        self.config_max_jitter_sec.set(sweep_config.max_jitter_sec)

    def update_receiver_config(self, receiver_config: ReceiverConfig):
        """
        Updates all gauges related to the receiver configuration.
        """
        self.receiver_config_gain_db.set(receiver_config.gain_db)
        self.receiver_config_bandwidth_hz.set(receiver_config.bandwidth_hz)
        self.receiver_config_duration_sec.set(receiver_config.duration_sec)

    async def run(self):
        app = web.Application()
        metrics_handler = make_aiohttp_handler(registry=self.registry)

        app.router.add_get("/metrics", metrics_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._listen_port)

        try:
            await site.start()
            logger.info(f"Metrics server started on port {self._listen_port}")
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
            logger.info("Metrics server shut down.")
