from typing import Protocol

from rf_survey.models import SweepConfig, ReceiverConfig


class IMetrics(Protocol):
    """
    Defines the contract for a metrics client.
    """

    def update_temperature(self, temp_c: float) -> None: ...

    def update_queue_size(self, size: int) -> None: ...

    def update_sweep_config(self, sweep_config: SweepConfig) -> None: ...

    def update_receiver_config(self, receiver_config: ReceiverConfig) -> None: ...

    async def run(self) -> None: ...


class IZmsMonitor(Protocol):
    """
    Defines the contract for a ZMS monitor.
    """

    async def run(self) -> None: ...
