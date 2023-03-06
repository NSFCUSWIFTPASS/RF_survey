# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import os
class Rsync(object):
    def __init__(self, bandwidth, interval, length, frequency ):
        self.bandwidth = str(bandwidth)
        self.interval = str(interval)
        self.length = str(length)
        self.frequency = str(frequency)

    def write_rsync(self):
        os.system("sed -i 's/BW=.*/BW=\""+self.bandwidth[:-6]+"\"/g' /home/pi/rsync.sh;"
                    "sed -i 's/INT=.*/INT=\""+self.interval+"\"/g' /home/pi/rsync.sh;"
                    "sed -i 's/LEN=.*/LEN=\""+self.length+"\"/g' /home/pi/rsync.sh;"
                    "sed -i 's/FREQ=.*/FREQ=\""+self.frequency[:-6]+"\"/g' /home/pi/rsync.sh")

