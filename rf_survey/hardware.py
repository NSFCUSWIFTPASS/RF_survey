# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import subprocess
import json
import os
import uhd
import uuid
from gpiozero import CPUTemperature
from datetime import datetime


def main():
    hardware = {}

    hardware["hostname"] = (subprocess.check_output("hostname")).decode("utf-8").strip()
    hex_mac = hex(uuid.getnode())
    hardware["rpi_mac"] = ":".join(
        ["{:02x}".format((uuid.getnode() >> ele) & 0xFF) for ele in range(0, 8 * 6, 8)][
            ::-1
        ]
    )
    try:
        hardware["rpi_ip"] = (
            (subprocess.check_output("hostname -I", shell=True))
            .decode("utf-8")
            .split()[0]
            .strip()
        )
    except Exception as e:
        print("%s" % (repr(e)))
    try:
        usrp = uhd.usrp.MultiUSRP("num_recv_frames=1024")
        hardware["usrp_sn"] = usrp.get_usrp_rx_info(0)["mboard_serial"]
        ref_loc = str(usrp.get_mboard_sensor("ref_locked", 0))[5:]
        hardware["sdr_op_status"] = "1"
        if ref_loc == "unlocked":
            hardware["ref_locked"] = "0"
        else:
            hardware["ref_locked"] = "1"
    except Exception as e:
        hardware["sdr_op_status"] = "0"
        hardware["usrp_sn"] = "XXXXXXX"
        hardware["ref_locked"] = "0"

    with open("/home/pi/rf_survey/location.json", "r") as f:
        location = json.load(f)
    hardware["location"] = location["location"]
    hardware["rpi_v"] = str(
        subprocess.check_output(
            'cat /proc/cpuinfo | grep -i "Raspberry Pi"', shell=True
        )
    )[13:-3]
    hardware["cpu_type"] = str(
        subprocess.check_output('cat /proc/cpuinfo | grep -i "model" -m 1', shell=True)
    )[16:-3]
    hardware["memory"] = int(
        (
            subprocess.check_output(
                "grep MemTotal /proc/meminfo | awk '{print $2;}'", shell=True
            )
        )
        .decode("utf-8")
        .strip()
    )
    hardware["cpu_cores"] = int(
        (subprocess.check_output("nproc", shell=True)).decode("utf-8").strip()
    )
    hardware["mboard_name"] = usrp.get_usrp_rx_info(0)["mboard_name"]
    hardware["os_v"] = (
        (
            subprocess.check_output(
                "grep PRETTY_NAME /etc/os-release | awk -F'\"' '$0=$2'", shell=True
            )
        )
        .decode("utf-8")
        .strip()
    )
    hardware["enclosure"] = "1"
    # needs to be updated for setups without network storage
    hardware["nfs_mnt"] = (
        (
            subprocess.check_output(
                "df | grep -i '192.168.0.50' | awk '{print $1}'", shell=True
            )
        )
        .decode("utf-8")
        .strip()
    )
    hardware["local_mnt"] = (
        (
            subprocess.check_output(
                "df | grep -i '192.168.0.50' | awk '{print $6}'", shell=True
            )
        )
        .decode("utf-8")
        .strip()
    )
    # todo: automate --> 0 if hardware['nfs_mnt'] is empty and change hardware['nfs_mnt'] to 'NA'
    hardware["mnt_op_status"] = "1"
    hardware["hardware_op_status"] = "1"
    hardware["rpi_op_status"] = "1"
    hardware["rpi_storage_cap"] = int(
        (subprocess.check_output("df | grep -i 'root' | awk '{print $2}'", shell=True))
        .decode("utf-8")
        .strip()
    )

    try:
        with open("/home/pi/wr_static.json", "r") as f:
            wr = json.load(f)
        hardware["wr_mac"] = "00:00:00:00:00:00"
        hardware["wr_ip"] = "192.168.0.10"
        hardware["wr_mode"] = wr["mode"]
        hardware["wr_serial"] = wr["serial"]
        hardware["wr_host"] = wr["wr_host"]
        hardware["wr_op_status"] = 1
    except:
        print("No WR-LEN attached.")
        hardware["wr_mac"] = None
        hardware["wr_ip"] = None
        hardware["wr_mode"] = None
        hardware["wr_serial"] = None
        hardware["wr_host"] = None
        hardware["wr_op_status"] = 0
    hardware["timestamp"] = datetime.now().strftime("%Y%m%dT%H%M%S")

    with open("/home/pi/sync/" + hardware["timestamp"] + "_hardware.json", "w+") as f:
        json.dump(hardware, f)


if __name__ == "__main__":
    main()
