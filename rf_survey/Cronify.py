# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

from crontab import CronTab

class Cronify(object):
    def __init__(self):
        self.cron = CronTab(user='pi')

    def create_job(self, config):
        self.command = "python3 /home/pi/rf_survey/rf_survey.py -f1 {} -f2 {} -b {} -s {} -g {} -r {} -t {} -c {} -d {} -o {} -gcs {} > /home/pi/rf_survey/cron.temp 2>&1 ".format(
            config['start_frequency'], 
            config['end_frequency'], 
            config['sampling_rate'],
            config['samples'],
            config['gain'],
            config['recordings'],
            config['interval'],
            config['cycles'],
            config['delay'],
            config['organization'],
            config['gcs']
        )
        crons = list(self.cron.find_comment('rfns'))
        if len(crons) == 0:
            self.job = self.cron.new(command=self.command, comment='rfns')
            self.job.every_reboot()
            self.cron.write()
        else:
            self.cron.remove_all(comment='rfns')
            self.job = self.cron.new(command=self.command, comment='rfns')
            self.job.every_reboot()
            self.cron.write()         

    def delete_job(self):
        self.cron.remove_all(comment='rfns')
        self.cron.write()