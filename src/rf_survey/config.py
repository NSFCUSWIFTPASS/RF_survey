import socket
from pydantic import SecretStr, computed_field, Field
from pydantic_settings import SettingsConfigDict, BaseSettings
from dataclasses import dataclass
from typing import Optional


@dataclass
class ZmsSettings:
    """Data structure for ZMS/ZMC heartbeat service configuration."""

    zmc_http: str
    token: SecretStr
    monitor_id: str
    monitor_schema_path: str


class AppSettings(BaseSettings):
    """Application settings, loaded from environment variables with an RF_ prefix."""

    NATS_HOST: str = "localhost"
    NATS_PORT: int = 4222
    NATS_TOKEN: SecretStr | None = None

    STORAGE_PATH: str
    LOG_LEVEL: str = "INFO"

    ZMS_ZMC_HTTP: str | None = None
    ZMS_TOKEN: SecretStr | None = None
    ZMS_MONITOR_ID: str | None = None
    ZMS_MONITOR_SCHEMA_PATH: str | None = None

    HOSTNAME: str = Field(default_factory=socket.gethostname)

    model_config = SettingsConfigDict(
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
            and self.ZMS_TOKEN
            and self.ZMS_MONITOR_ID
            and self.ZMS_MONITOR_SCHEMA_PATH
        ):
            return ZmsSettings(
                zmc_http=self.ZMS_ZMC_HTTP,
                token=self.ZMS_TOKEN,
                monitor_id=self.ZMS_MONITOR_ID,
                monitor_schema_path=self.ZMS_MONITOR_SCHEMA_PATH,
            )
        return None


settings = AppSettings()
