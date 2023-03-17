#!/bin/bash
source $HOME/.profile

ScriptName="$(basename $0)"

if [ $(/bin/pidof -x ${ScriptName}| /bin/wc -w) -gt 2 ]; then
    exit
else
    /usr/bin/python3 /root/server/Watcher.py
fi
