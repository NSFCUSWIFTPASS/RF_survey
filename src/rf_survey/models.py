import random
from dataclasses import dataclass, field
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from uuid import uuid4
from datetime import datetime

from rf_survey.utils.scheduler import calculate_wait_time


class SweepConfig(BaseModel):
    start_hz: int
    end_hz: int
    step_hz: int
    cycles: int
    records_per_step: int
    interval_sec: int
    max_jitter_sec: float

    @model_validator(mode="after")
    def end_must_be_gte_start(self) -> "SweepConfig":
        if self.end_hz < self.start_hz:
            raise ValueError("end_hz cannot be less than start_hz")
        return self

    def next_collection_wait_duration(self) -> float:
        """
        Calculates the total time to wait until the next collection,
        including jitter. This is the logic moved from the old wait function.
        """
        jitter_duration = 0.0
        if self.max_jitter_sec > 0:
            jitter_duration = random.uniform(0, self.max_jitter_sec)

        base_wait_duration = calculate_wait_time(self.interval_sec)
        return base_wait_duration + jitter_duration


class ReceiverConfig(BaseModel):
    gain_db: int = Field(..., ge=0, le=76)
    bandwidth_hz: int = Field(..., gt=0)
    duration_sec: float = Field(..., gt=0)

    @property
    def num_samples(self) -> int:
        return int(self.duration_sec * self.bandwidth_hz)


@dataclass
class RawCapture:
    """
    Holds the direct, unprocessed output of a single hardware capture.
    """

    # The raw binary data, ready to be saved to a file.
    iq_data_bytes: bytes

    # The exact center frequency used for this capture.
    center_freq_hz: int

    # The precise hardware timestamp of the first sample.
    capture_timestamp: datetime


@dataclass
class CaptureResult:
    """A container for a raw capture and the exact config used to create it."""

    raw_capture: RawCapture
    receiver_config: ReceiverConfig


@dataclass
class ProcessingJob:
    """
    Holds the data for the main app loop to communicate to other services.
    """

    raw_capture: RawCapture
    receiver_config_snapshot: ReceiverConfig
    sweep_config_snapshot: SweepConfig


class ApplicationInfo(BaseModel):
    """
    Holds static information on the application runtime.
    """

    hostname: str
    organization: str
    coordinates: str
    output_path: Path
    group: str = field(default_factory=lambda: str(uuid4()))
