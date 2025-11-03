from typing import Callable, Awaitable, Dict, Any, Optional
from zmsclient.zmc.v1.models import MonitorStatus

ReconfigurationCallback = Callable[
    [MonitorStatus, Optional[Dict[str, Any]]], Awaitable[None]
]
