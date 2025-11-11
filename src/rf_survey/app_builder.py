from rf_shared.nats_client import NatsProducer

from rf_survey.app import SurveyApp
from rf_survey.config import AppSettings
from rf_survey.metrics import Metrics, NullMetrics
from rf_survey.models import SweepConfig, ApplicationInfo
from rf_survey.receiver import Receiver
from rf_survey.monitor import NullZmsMonitor
from rf_survey.watchdog import ApplicationWatchdog
from rf_survey.monitor_factory import initialize_zms_monitor


class SurveyAppBuilder:
    def __init__(
        self,
        app_info: ApplicationInfo,
        settings: AppSettings,
        sweep_config: SweepConfig,
        receiver: Receiver,
        producer: NatsProducer,
        watchdog: ApplicationWatchdog,
    ):
        self.app_info = app_info
        self.settings = settings
        self.sweep_config = sweep_config
        self.receiver = receiver
        self.producer = producer
        self.watchdog = watchdog
        self.metrics = NullMetrics()
        self.zms_monitor = NullZmsMonitor()
        self._zms_enabled = False

    def with_metrics(self, metrics: Metrics) -> "SurveyAppBuilder":
        self.metrics = metrics
        return self

    def with_zms(self) -> "SurveyAppBuilder":
        self._zms_enabled = True
        return self

    async def build(self) -> SurveyApp:
        app = SurveyApp(
            app_info=self.app_info,
            sweep_config=self.sweep_config,
            receiver=self.receiver,
            producer=self.producer,
            watchdog=self.watchdog,
            zms_monitor=self.zms_monitor,
            metrics=self.metrics,
        )

        if self._zms_enabled:
            real_zms_monitor = await initialize_zms_monitor(
                settings=self.settings,
                reconfiguration_callback=app.apply_zms_reconfiguration,
            )
            app.zms_monitor = real_zms_monitor

        # ZMS controls whether or not we are running
        # so if ZMS is disabled start up immediately
        if isinstance(app.zms_monitor, NullZmsMonitor):
            await app.start_survey()

        return app
