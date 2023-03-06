# CU PASS RFBS Monitoring

Monitoring is crucial to track the health of RPis in the field and to identify threats to active RFBS surveys that could lead to data corruption, data loss, or system failure. These scripts are offered as a lightweight, open-source monitoring solution but are not required to run RFBS surveys.

## Requirements

### Dependencies
Ensure the following packages are installed on your system:
```sh
apt install mail sysstat zip 
```

### File Permissions
Do not edit and save monitoring files as root. All monitoring files should be owned by `pi:pi`. Most should be made executable.
Move the monitoring script folder to user pi home directory.
```sh
cp -r ~/src/rf-baseline-noise-survey/rpi/monitoring/ ~/monitoring
```

### Crontab
Most of these scripts run in crontab. Here is the recommended text to add at the bottom of your crontab:

```sh
*/10 * * * * ~/monitoring/rpi_health/disk_alert.sh; ~/monitoring/rpi_health/health_monitor.sh
59 23 * * * ~/monitoring/log_rotate.sh
59 23 * * * ~/health_report.sh
59 23 * * 6 ~/monitoring/logins/login_report.sh
```

### MSMTP
Several of these scripts utilize `mail`. Ensure msmtp is properly configured. The msmtp system configuration file is `/etc/msmtp` and is owned by `root:root`. Here is the recommended file (requires sudo to edit):
```sh
# Generics:
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt

# User specific log location:
logfile        ~/tmp/.msmtp.log
# Otherwise use /var/log/msmtp.log, 
# however, this will create an access violation if you 
# are user pi, and have not changed the access rights

# Gmail specifics:
# You will need to create an 'app password' in Gmail
account        gmail
host           smtp.gmail.com
port           587

from           [YOUR-GMAIL]@gmail.com
user           [YOUR-GMAIL]@gmail.com
password       [APP PASSWORD]

# Default:
account default : gmail
```


## Troubleshooting
If you are experiencing issues with the functionality of these bash scripts, please refer to the RFBS Controller Handbook for troubleshooting.