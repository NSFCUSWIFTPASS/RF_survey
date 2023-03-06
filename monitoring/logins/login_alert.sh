#!/bin/bash
#
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Georgiana Weihe.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# OPTIONAL: Alerts when a login event occurs
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# The RFBS GUI logs in to the RPi to execute survey stop/start. 
# Tracking logins is situationally useful
# -- when a remote survey is running (login event could = tampered survey)
# -- to track logins from the GUI (login = survey stop/start)
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
# To implement, place this code at the bottom of /etc/profile 
# prior to running a survey
#:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

HOSTNAME=`/bin/hostname`
DATE=`/bin/date`
ID=`/bin/whoami`
echo " " | mail -s "Login Occured on $HOSTNAME for user: $ID $DATE" raspberrypisurveyalert@gmail.com
