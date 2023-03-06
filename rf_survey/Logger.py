# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import os
import logging
from datetime import time
from logging.handlers import TimedRotatingFileHandler
from syslog import syslog

class Logger(object):
    def __init__(self, key, path, log_file):
        self.key = key
        self.path = path
        self.log_file = log_file
        if not os.path.exists(self.path):
            try:
                os.makedirs(self.path)
            except:
                print("Error when creating directory")
    
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # create logger
        self.logger = logging.getLogger(str(self.key).lower())
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            self.logger.propagate = 0
            handler = TimedRotatingFileHandler(self.path+self.log_file, when="D", interval=1, atTime=time(0,0,1))
            handler.suffix = "%Y%m%d"
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.handlers = []
            self.logger.addHandler(handler)
    
    def write_log(self, level, message):
        # writes to a local log as well as syslog
        if level == "INFO":
            self.logger.info(message)
        if level == "DEBUG":
            self.logger.debug(message)
        if level == "WARNING":
            self.logger.warning(message)
        if level == "ERROR":
            self.logger.error(message)
        if level == "CRITICAL":
            self.logger.critical(message)
        syslog(message)