from dataclasses import dataclass

from zmsclient.zmc.v1.models import MonitorPending


@dataclass
class ProcessReconfigurationCommand:
    """Command to process a new MonitorPending configuration."""

    pending: MonitorPending


MonitorCommand = ProcessReconfigurationCommand
