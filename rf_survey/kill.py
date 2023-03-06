# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

# Simple code executed to gracefully kill a running data collection process.
# It reads the PID created by sweeps.py and sends the termination signal to the PID

import os
from signal import SIGTERM

with open(os.environ["HOME"]+"/sweeps.pid", "r") as f:
    pid = int(f.readline())
os.kill(pid, SIGTERM)