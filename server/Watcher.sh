#!/bin/bash
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

source $HOME/.profile

ScriptName="$(basename $0)"

if [ $(/bin/pidof -x ${ScriptName}| /bin/wc -w) -gt 2 ]; then
    exit
else
    /usr/bin/python3 /root/server/Watcher.py
fi
