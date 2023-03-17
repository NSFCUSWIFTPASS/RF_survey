# Simple code executed to gracefully kill a running script.
# It reads the PID created by Watcher.py and sends the termination signal to the PID

import os
from signal import SIGTERM

with open(os.environ["HOME"]+"/watcher.pid", "r") as f:
    pid = int(f.readline())
os.kill(pid, SIGTERM)
