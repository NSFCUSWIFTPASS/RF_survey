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
print(hostname)
host = "192.168.0.10"

ip = socket.gethostbyname(host)
print(ip)

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
    "wr0_rx":stats['wr0_rx'],
    "wr0_tx":stats['wr0_tx'],
    "wr1_rx":stats['wr1_rx'],
    "wr1_tx":stats['wr1_tx'],
    "wr0_lnk":stats['wr0_lnk'],
    "wr1_lnk":stats['wr1_lnk'],
    "wr0_setp":stats['wr0_setp'],
    "wr0_cko":stats['wr0_cko'],
    "wr0_mu":stats['wr0_mu'],
    "wr0_crtt":stats['wr0_crtt'],
    "wr0_ucnt":stats['wr0_ucnt'],
    "mode":stats['mode'].encode('ascii'),
    "wr0_ss":stats['wr0_ss'].encode('ascii'),
    "serial":stats['serial'].encode('ascii'),
    "wr_host":"hcro-rpi-003",
    "wr_op_status":1}

    # Write dictionary to JSON file
    with open("/home/pi/wr_dynamic.json", "w+") as outfile:
        json.dump(dynamic_stats, outfile)

    print("Data written to JSON file")
    print(dynamic_stats['serial'])
except:
    print("Error while polling %s" % host)
    dynamic_stats = {"wr_temp": None,
            "wr0_rx": None,
            "wr0_tx": None,
            "wr1_rx": None,
            "wr1_tx": None,
            "wr0_lnk": None,
            "wr1_lnk": None,
            "wr0_setp": None,
            "wr0_cko": None,
            "wr0_mu": None,
            "wr0_crtt": None,
            "wr0_ucnt": None,
            "wr0_ss": None,
            "serial": "",
            "wr_host": "",
            "wr_op_status": 0}
    with open("/home/pi/wr_dynamic.json", "w+") as outfile:
        json.dump(dynamic_stats, outfile)
