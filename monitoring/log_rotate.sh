#!/bin/bash
#
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Georgiana Weihe.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# Rotates some logs
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# This file should be made executable and placed in a crontab. 
# Choose a duration for log files by changing the frequency of 
# log_rotate.sh run in cron. For example,
#
# 59 23 * * * /home/pi/monitoring/log_rotate.sh
# rotates logs nightly at 23:59 (preferrd)
# 
# or
# 
# 59 23 * * 6 /home/pi/monitoring/log_rotate.sh
# rotates logs once a week on Saturday at 23:59
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

# Rotate only:
mv /home/pi/rsync.log /home/pi/logs/rsync_`date +%F`.log
mv /home/pi/.msmtp.log /home/pi/logs/msmtp_`date +%F`.log

# Email a copy and rotate:
mail -s "Daily Temperature Log for "`/bin/hostname` raspberrypisurveyalert@gmail.com < /tmp/temp_report.txt
mv /tmp/temp_report.txt /home/pi/logs/temperature_`/bin/date +%F`.log

mail -s "Daily CPU Log for "`/bin/hostname` raspberrypisurveyalert@gmail.com < /tmp/cpu_log.txt
mv /tmp/cpu_log.txt /home/pi/logs/cpu_`/bin/date +%F`.log 
