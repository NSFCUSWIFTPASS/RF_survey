# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import os
import shutil
import json
import psycopg2
import subprocess
from configparser import ConfigParser
from Logger import Logger
from datetime import datetime

class Hardware(object):
    def __init__(self, filename):
        self.filename = filename
        self.time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"]+"/logs/"
        self.logger = Logger("hardware", log_path,"data_log-"+self.time+".log")

    def update_db(self):
        with open(self.filename) as f:
            hardware = dict(json.load(f).items())
        try:
            hardware['nfs_storage_cap'] = int((subprocess.check_output("df | grep -i '/dev/sda' | awk 'NR==1{print $2}'", shell=True)).decode('utf-8'))
            hardware['storage_op_status'] = 1
        except Exception as e:
            hardware['nfs_storage_cap'] = 0
            hardware['storage_op_status'] = 0
            self.logger.write_log("ERROR", "Could not read server storage capacity: %s."%(repr(e)))
            
        """Update tables in the PostgreSQL database"""
        select = """
            SELECT hardware_id FROM rpi WHERE hostname = %s;
            """
        update = """
            UPDATE hardware SET (location, enclosure, op_status, mount_id) = (%s,%s,%s,%s) WHERE hardware_id=%s;
            """
        commands = (
            """
            INSERT INTO storage(nfs_mnt, local_mnt, storage_cap, op_status) VALUES (%s, %s, %s, %s) 
                ON CONFLICT (nfs_mnt) DO UPDATE SET nfs_mnt=%s, local_mnt=%s, storage_cap=%s, op_status=%s
                RETURNING mount_id;
            """,
            """
            INSERT INTO hardware(location, enclosure, op_status, mount_id) VALUES(%s,%s,%s,%s) 
                RETURNING hardware_id;
            """,
            """
            INSERT INTO rpi(hostname, rpi_ip, rpi_mac, rpi_v, os_v, memory, storage_cap, cpu_type, cpu_cores, op_status, hardware_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) 
                ON CONFLICT (hostname) DO UPDATE SET hostname=%s, rpi_ip=%s, rpi_mac=%s, rpi_v=%s, os_v=%s, memory=%s, storage_cap=%s, cpu_type=%s, cpu_cores=%s, op_status=%s, hardware_id=%s;
            """,
            """
            INSERT INTO sdr(sdr_serial, mboard_name, external_clock, op_status, hardware_id) VALUES(%s,%s,%s,%s,%s) 
                ON CONFLICT (sdr_serial) DO UPDATE SET sdr_serial=%s, mboard_name=%s, external_clock=%s, op_status=%s, hardware_id=%s;
            """,
            """
            INSERT INTO wrlen(wr_serial, wr_ip, wr_mac, mode, wr_host, op_status, hardware_id) VALUES(%s,%s,%s,%s,%s,%s,%s) 
                ON CONFLICT (wr_serial) DO UPDATE SET wr_serial=%s, wr_ip=%s, wr_mac=%s, mode=%s, wr_host=%s, op_status=%s, hardware_id=%s;
            """
        )

        conn = None
        try:
            # read connection parameters
            parser = ConfigParser()
            # read config file
            parser.read("database.ini")

            # get section, default to postgresql
            db = {}
            if parser.has_section("postgresql"):
                params = parser.items("postgresql")
                for param in params:
                    db[param[0]] = param[1]
            else:
                raise Exception("Section {0} not found in the {1} file".format("postgresql", "database.ini"))
            # connect to the PostgreSQL server
            print("Connecting to the PostgreSQL database...")
            conn = psycopg2.connect(**db)
            print("Connection successful.")
            # create a cursor
            cur = conn.cursor()
            # execute a statement
            cur.execute(select,[hardware['hostname']])
            row = cur.fetchone()
            print("hardware: select executed")
            cur.execute(commands[0], (hardware['nfs_mnt'], hardware['local_mnt'], hardware['nfs_storage_cap'], hardware['mnt_op_status'],hardware['nfs_mnt'], hardware['local_mnt'], hardware['nfs_storage_cap'], hardware['mnt_op_status'],))
            mount_id = cur.fetchone()
            print("hardware: Commands 1 executed.")
            if row is not None:
                hardware_id = row[0]
                cur.execute(update, (hardware['location'], hardware['enclosure'], hardware['hardware_op_status'], mount_id, hardware_id,))
            else:
                cur.execute(commands[1], (hardware['location'], hardware['enclosure'], hardware['hardware_op_status'], mount_id,))
                hardware_id = cur.fetchone()
            print("hardware: Commands 2 executed.")
            cur.execute(commands[2], (hardware['hostname'],
                                      hardware['rpi_ip'],
                                      hardware['rpi_mac'],
                                      hardware['rpi_v'],
                                      hardware['os_v'],
                                      hardware['memory'],
                                      hardware['rpi_storage_cap'],
                                      hardware['cpu_type'],
                                      hardware['cpu_cores'],
                                      hardware['rpi_op_status'],
                                      hardware_id,
                                      hardware['hostname'],
                                      hardware['rpi_ip'],
                                      hardware['rpi_mac'],
                                      hardware['rpi_v'],
                                      hardware['os_v'],
                                      hardware['memory'],
                                      hardware['rpi_storage_cap'],
                                      hardware['cpu_type'],
                                      hardware['cpu_cores'],
                                      hardware['rpi_op_status'],
                                      hardware_id,  
                                ))
            print("hardware: Commands 3 executed.")
            cur.execute(commands[3], (hardware['usrp_sn'], hardware['mboard_name'], hardware['ref_locked'], hardware['sdr_op_status'], hardware_id, hardware['usrp_sn'], hardware['mboard_name'], hardware['ref_locked'], hardware['sdr_op_status'], hardware_id,))
            if hardware['wr_serial']:
                cur.execute(commands[4], (hardware['wr_serial'], hardware['wr_ip'], hardware['wr_mac'], hardware['wr_mode'], hardware['wr_host'], hardware['wr_op_status'], hardware_id, hardware['wr_serial'], hardware['wr_ip'], hardware['wr_mac'], hardware['wr_mode'], hardware['wr_host'], hardware['wr_op_status'], hardware_id,))
            # close the communication with the PostgreSQL server
            cur.close()
            conn.commit()
            print("hardware: Commands 4 executed.")
            self.logger.write_log("INFO", "Hardware information added to database")
            os.remove(self.filename)
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            self.logger.write_log("ERROR", "Could not write to datbase due to %s."%(repr(error)))
            # TODO: move file to a different location for inspection if an error occurs
            return
        finally:
            if conn is not None:
                conn.close()
                print("Database connection closed.")
