from pydantic import BaseModel, Field, ValidationError, model_validator, PositiveInt


class ZmsReconfigurationParams(BaseModel):
    """
    A Pydantic model to validate and parse raw ZMS parameters, with constraints
    based on the known capabilities of a USRP B200/B210 SDR.
    """

    gain_db: int = Field(
        ...,
        ge=0,
        le=76,
        description="RX Gain in dB. Valid range for B200/B210 is 0-76 dB.",
    )
    duration_sec: float = Field(
        ...,
        ge=0.01,
        le=10.0,
        description="Capture duration in seconds for each frequency step.",
    )
    bandwidth_hz: PositiveInt = Field(
        ...,
        ge=200_000,
        le=56_000_000,
        description="Instantaneous bandwidth in Hz. For B200/B210, max is 56 MHz.",
    )

    start_freq_hz: PositiveInt = Field(
        ...,
        ge=70_000_000,
        le=6_000_000_000,
        description="Sweep start frequency in Hz. B200/B210 range is 70 MHz to 6 GHz.",
    )
    end_freq_hz: PositiveInt = Field(
        ...,
        ge=70_000_000,
        le=6_000_000_000,
        description="Sweep end frequency in Hz. B200/B210 range is 70 MHz to 6 GHz.",
    )
    sample_interval: int = Field(
        ...,
        ge=1,
        le=10,
        description="Time in seconds between the start of consecutive samples.",
    )

    @model_validator(mode="after")
    def check_frequency_logic(self) -> "ZmsReconfigurationParams":
        """Ensures the start and end frequencies are logically consistent."""
        if self.end_freq_hz < self.start_freq_hz:
            raise ValidationError("end_freq_hz cannot be less than start_freq_hz")
        return self
