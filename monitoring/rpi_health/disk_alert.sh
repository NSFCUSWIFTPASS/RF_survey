#!/bin/bash
#
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# Alerts if disk is filling up
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# This file should be made executable and placed in a crontab. 
# Add this line to crontab:
# */10 * * * * /home/pi/monitoring/rpi_health/disk_alert.sh
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# Set $ADMIN to the email the notification should be sent to.
ADMIN="raspberrypisurveyalert@gmail.com"

# Threshold beyond which an alert is sent out (e.g. 50%)
# this is a 64 GB card, so we alert at 35% utilization
# normal utilization during a survey is 10-12%
ALERT=35

# Create a list of partitions that shouldnt be monitored
# Use "|" to separate multiple partitions.
# An example: EXCLUDE_LIST="/dev/hdd1|/dev/hdc5"
EXCLUDE_LIST="/dev/mmcblk0p1"

#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
#

function main_prog() {
while read output;
do
#echo $output
  usep=$(echo $output | awk '{ print $1}' | cut -d'%' -f1)
  partition=$(echo $output | awk '{print $2}')
  if [ $usep -ge $ALERT ] ; then
     echo "Running out of space \"$partition ($usep%)\" on server $(hostname), $(date)" | \
     mail -s "Alert: Above average disk space $usep%" $ADMIN
  fi
done
}

if [ "$EXCLUDE_LIST" != "" ] ; then
  df -H | grep -vE "^Filesystem|tmpfs|cdrom|${EXCLUDE_LIST}" | awk '{print $5 " " $6}' | main_prog
else
  df -H | grep -vE "^Filesystem|tmpfs|cdrom" | awk '{print $5 " " $6}' | main_prog
fi
