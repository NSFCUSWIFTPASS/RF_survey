#!/bin/bash
#
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Georgiana Weihe.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# OPTIONAL: Emails admin all logins from previous week
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# The RFBS GUI logs in to the RPi to execute survey stop/start. 
# Tracking logins is situationally useful
# -- when a remote survey is running (login event could = tampered survey)
# -- to track logins from the GUI (login = survey stop/start)
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# To implement, make this file executable and place it in crontab. 
# Add this line to crontab:
# 58 23 * * 6 /home/pi/monitoring/logins/login_report.sh
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

last -as "`/bin/date -d last-sunday +%Y-%m-%d`" > /tmp/login_report.txt; mail -s "Weekly Login Report for "`/bin/hostname` raspberrypisurveyalert@gmail.com < /tmp/login_report.txt
mv /tmp/login_report.txt /home/pi/logs/login-log-`date +%F`.log
