# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

'''
Simple script to poll WR-LEN endpoints by hostname and
write dynamic stats to JSON file
'''

import socket
import argparse
import time
import datetime
import os
import json
from wr_cm.wr_len import WrLen
from wr_cm import __version__

hostname = socket.gethostname()

host = "192.168.0.10"#hardware['wr_ip']

print('Begging WR-LEN status polling')
wr_devices = {}

if host not in wr_devices.keys():
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        print(repr(e))
    try:
        wr_devices[host] = WrLen(host)
    except:
        print("Error while connecting to %s" % host)
print("polling %s" % (host))
try:
    stats = wr_devices[host].gather_keys(include_ver=False)

    # Create dictionary of dynamic stats from WR-LENs and convert to JSON
    dynamic_stats = {"temp":stats['temp'].encode('ascii'),
    "timestamp":stats['timestamp'].encode('ascii'),
    "mode":stats['mode'].encode('ascii'),
    "serial":stats['serial'].encode('ascii'),
    "wr_host":"hostname", "wr_op_status":1}

    # Write dictionary to JSON file
    with open("wr_static.json", "w+") as outfile:
        json.dump(dynamic_stats, outfile)

    print("Data written to JSON file")    

except:
    print("Error while polling %s" % host)
    dynamic_stats = {"wr_op_status":0}
