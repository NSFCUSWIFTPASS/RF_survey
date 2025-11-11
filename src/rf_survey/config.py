import socket
from pydantic import SecretStr, computed_field, Field
from pydantic_settings import SettingsConfigDict, BaseSettings
from dataclasses import dataclass
from typing import Optional


@dataclass
class ZmsSettings:
    """Data structure for ZMS/ZMC heartbeat service configuration."""

    zmc_http: str
    identity_http: str
    token: SecretStr
    monitor_id: str
    monitor_schema_path: str


class AppSettings(BaseSettings):
    """Application settings, loaded from environment variables with an RF_ prefix."""

    FREQUENCY_START: int = 915_000_000
    FREQUENCY_END: int = 915_000_000
    BANDWIDTH: int = 20_000_000
    DURATION_SEC: float = 1.0
    GAIN: int = 35
    ORGANIZATION: str = "DefaultOrg"
    COORDINATES: str = "0.0N,0.0W"
    RECORDS: int = 1
    CYCLES: int = 1
    TIMER: int = 10
    JITTER: float = 0.0

    NATS_HOST: str = "localhost"
    NATS_PORT: int = 4222
    NATS_TOKEN: Optional[SecretStr] = None
    STORAGE_PATH: str = "/tmp"
    LOG_LEVEL: str = "INFO"

    ZMS_ZMC_HTTP: Optional[str] = None
    ZMS_IDENTITY_HTTP: Optional[str] = None
    ZMS_TOKEN: Optional[SecretStr] = None
    ZMS_MONITOR_ID: Optional[str] = None
    ZMS_MONITOR_SCHEMA_PATH: Optional[str] = None

    METRICS_ENABLED: bool = False
    METRICS_PORT: int = 9090

    HOSTNAME: str = Field(default_factory=socket.gethostname)

    model_config = SettingsConfigDict(
        extra="allow",
        env_prefix="RF_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @computed_field
    @property
    def NATS_URL(self) -> str:
        """
        Dynamically constructs the NATS connection URL.
        """
        return f"nats://{self.NATS_HOST}:{self.NATS_PORT}"

    @computed_field
    @property
    def NATS_SUBJECT(self) -> str:
        """Dynamically constructs the NATS subject for this host."""
        return f"jobs.rf.{self.HOSTNAME}"

    @computed_field
    @property
    def zms(self) -> Optional[ZmsSettings]:
        """
        Constructs a ZmsSettings object if all required environment
        variables are present, otherwise returns None.
        """
        if (
            self.ZMS_ZMC_HTTP
            and self.ZMS_IDENTITY_HTTP
            and self.ZMS_TOKEN
            and self.ZMS_MONITOR_ID
            and self.ZMS_MONITOR_SCHEMA_PATH
        ):
            return ZmsSettings(
                zmc_http=self.ZMS_ZMC_HTTP,
                identity_http=self.ZMS_IDENTITY_HTTP,
                token=self.ZMS_TOKEN,
                monitor_id=self.ZMS_MONITOR_ID,
                monitor_schema_path=self.ZMS_MONITOR_SCHEMA_PATH,
            )
        return None


app_settings = AppSettings()
