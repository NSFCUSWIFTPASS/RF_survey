#!/bin/bash
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

ScriptName="$(basename $0)"
PATH="/data/data/"
SERVER="192.168.0.50"
USER="user"

if [ $(/bin/pidof -x ${ScriptName}| /bin/wc -w) -gt 2 ]; then 
    exit
else
    /bin/rsync -a --log-file=rsync.log --rsync-path="mkdir -p ${PATH} && rsync" --rsh="/bin/ssh -i /home/pi/.ssh/id_rsa" /home/pi/sync/ ${USER}@${SERVER}:$PATH --progress --remove-source-files
fi
