#!/bin/bash
#
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Georgiana Weihe.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# Logs important metrics.
# Alerts if metrics go above thresholds.
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# This file should be made executable and placed in a crontab. 
# Ensure this line is in crontab:
# */10 * * * * /home/pi/monitoring/rpi_health/health_monitor.sh
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

HOST=$(hostname)
DATE=$(date)
CPU=$(sar 1 5 | grep "Average" | sed 's/^.* //')
CPU=$( printf "%.0f" $CPU )
CPU_TEMP=$(</sys/class/thermal/thermal_zone0/temp)
CPU_TEMP=$((CPU_TEMP/1000))
GPU_TEMP=$(vcgencmd measure_temp | egrep -o '[0-9*\.[0-9]*')

# Logs self reported temp of RPi
echo "$DATE --------- GPU = $GPU_TEMP Celsius, CPU = $CPU_TEMP Celsius" >> /tmp/temp_report.txt

# Logs CPU idle
echo "$DATE CPU idle is $CPU" >> /tmp/cpu_log.txt

# Alerts if CPU idle is under 20
if [ "$CPU" -lt 20 ]
then
	echo " " | mail -s "Alert: CPU utilization on $HOST is high (above 80%)" raspberrypisurveyalert@gmail.com
fi

# Alerts if RPi temp dangerously high (over 80C is bad)
if [ "$CPU_TEMP" -gt 75 ]
then
	echo " " | mail -s "Alert: temperature on $HOST is high ($CPU_TEMP Celsius)" raspberrypisurveyalert@gmail.com
fi
