# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import os
import sys
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class Logger:
    def __init__(self, name: str, log_path: str = "~/logs", log_level: str = "INFO"):
        self.name = name.lower()

        self.log_path = os.path.expanduser(log_path)

        log_time = datetime.now().strftime("%Y-%m-%d")
        self.log_file = f"{self.name}-{log_time}.log"

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)

        # check if handlers are already present
        if self.logger.hasHandlers():
            return

        self.logger.propagate = False

        try:
            os.makedirs(self.log_path, exist_ok=True)

            # file handler
            file_handler = TimedRotatingFileHandler(
                os.path.join(self.log_path, self.log_file),
                when="midnight",
                interval=1,
                backupCount=7,
                utc=True,
            )

            file_handler.setLevel(log_level.upper())
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        except (OSError, IOError) as e:
            print(
                f"ERROR: Could not configure logger '{self.name}'. Error: {e}",
                file=sys.stderr,
            )  # fall back to stderr

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
