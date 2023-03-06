# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import json
import os
import time
from dateutil.relativedelta import relativedelta
from datetime import datetime

class Restoration(object):
    def check_pulse(self):
        if os.path.exists(os.environ["HOME"]+"/lifesigns.json"):
            with open(os.environ["HOME"]+"/lifesigns.json") as file:
                self.configs = json.load(file)
            
            start_time = datetime.strptime(self.configs['start_time'], "%Y-%m-%d %H:%M:%S.%f")+ relativedelta(seconds=self.configs['delay'])
            
            seconds = float(start_time.strftime('%S.%f'))
            next_interval = int(seconds//self.configs['interval'] * self.configs['interval'] + self.configs['interval'])
            
            if next_interval >= 60:
                next_second = ((start_time.minute * 60 + start_time.second) // next_interval + 1) * next_interval % 60
                minutes = next_interval // 60
                minute_delta = abs(start_time.minute - ((start_time.minute // minutes + 1) * minutes))
                self.start_time = datetime(start_time.year, start_time.month, start_time.day, start_time.hour, start_time.minute, next_second, 0) + relativedelta(minutes=+minute_delta)
            else:
                next_second = next_interval
                self.start_time = datetime(start_time.year, start_time.month, start_time.day, start_time.hour, start_time.minute, next_second, 0)

            self.steps = (self.configs['end_frequency'] - self.configs['start_frequency']) / self.configs['sampling_rate'] + 1
            if self.configs["cycles"] == 0:
                end_time = datetime.today() + relativedelta(minutes=+1)
            else:
                end_time = self.start_time + relativedelta(seconds=+(self.steps * self.configs['recordings'] * self.configs['cycles'] * self.configs['interval']))
            
            if end_time < datetime.today():
                return 2
            else:
                return 1
        else:
            return 0

    def cardioversion(self):
        
        time.sleep(30)

        now = datetime.today()
        difference = (now - (self.start_time)).total_seconds()

        prior_recordings = int(difference // self.configs['interval'] + 1)

        if self.configs['start_frequency'] != self.configs['end_frequency']:
            steps = self.steps 
            n_cycles = int(prior_recordings // (steps * self.configs['recordings']))
            n_recordings = int(prior_recordings % (steps * self.configs['recordings']))
            recordings_left = self.configs['recordings'] - n_recordings % self.configs['recordings']
            start_index = self.configs['recordings']-recordings_left
            next_frequency = self.configs['start_frequency'] + self.configs['sampling_rate'] * (n_recordings//self.configs['recordings'])
        else:
            steps = 1
            n_cycles = 1
            recordings_left = self.configs['recordings'] - prior_recordings
            start_index = self.configs['recordings'] - recordings_left
            next_frequency = self.configs['start_frequency']

        if self.configs['cycles'] != 0:
            cycles_left = max(self.configs['cycles'] - n_cycles, 1)
        else:
            cycles_left = 0

        return next_frequency, cycles_left, self.configs['group'], start_index, self.start_time #self.configs['start_time']