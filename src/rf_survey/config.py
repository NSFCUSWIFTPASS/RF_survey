import socket
from pydantic import SecretStr, computed_field, Field
from pydantic_settings import SettingsConfigDict, BaseSettings


class AppSettings(BaseSettings):
    """Application settings, loaded from environment variables with an RF_ prefix."""

    NATS_HOST: str = "localhost"
    NATS_PORT: int = 4222
    NATS_TOKEN: SecretStr | None = None

    STORAGE_PATH: str
    LOG_LEVEL: str = "INFO"

    HOSTNAME: str = Field(default_factory=socket.gethostname)

    model_config = SettingsConfigDict(
        env_prefix="RF_", env_file=".env", env_file_encoding="utf-8"
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


settings = AppSettings()
