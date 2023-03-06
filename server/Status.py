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

class Status(object):
    def __init__(self, filename):
        self.filename = filename
        self.time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"]+"/logs/"
        self.logger = Logger("status", log_path,"data_log-"+self.time+".log")

    def update_db(self):
        with open(self.filename) as f:
            status = dict(json.load(f).items())
        try:
            status['rem_nfs_storage_cap'] = int((subprocess.check_output("df | grep -i '/dev/sda' | awk 'NR==1{print $4}'", shell=True)).decode('utf-8'))
            status['storage_op_status'] = 1
        except Exception as e:
            status['rem_nfs_storage_cap'] = 0
            status['storage_op_status'] = 0
            self.logger.write_log("ERROR", "Could not read local storage"%(repr(e)))
            
        """Update tables in the PostgreSQL database"""

        select = ("""
            SELECT hardware_id FROM rpi WHERE hostname = %s;
            """,
                  """
                  SELECT mount_id FROM hardware WHERE hardware_id = %s;
                  """)

        commands = ("""
            INSERT INTO status(hostname, time, rpi_cpu_temp, sdr_temp, avg_cpu_usage, bytes_recorded, rem_nfs_storage_cap, rem_rpi_storage_cap, rpi_uptime_minutes, hardware_id, wr_servo_state, wr_sfp1_link, wr_sfp2_link, wr_sfp1_tx, wr_sfp1_rx, wr_sfp2_tx, wr_sfp2_rx, wr_phase_setp, wr_rtt, wr_crtt, wr_clck_offset, wr_updt_cnt, wr_temp, wr_host)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
            """,
                    """
                    UPDATE hardware SET op_status = %s WHERE hardware_id = %s;
                    """,
                   """
                   UPDATE storage SET op_status = %s WHERE mount_id = %s;
                   """,
                   """
                   UPDATE rpi SET op_status = %s WHERE hardware_id = %s;
                   """,
                   """
                   UPDATE sdr SET op_status = %s WHERE hardware_id = %s;
                   """,
                   """
                   UPDATE wrlen SET op_status = %s WHERE hardware_id = %s;
                   """,)

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
            cur.execute(select[0], [status['hostname']])
            print("status: select executed")
            hardware_id = cur.fetchone()[0]
            cur.execute(select[1], [hardware_id])
            mount_id = cur.fetchone()[0]
            cur.execute(commands[0], (status['hostname'],
                                status['time'],
                                status['rpi_cpu_temp'],
                                status['sdr_temp'],
                                status['avg_cpu_usage'],
                                status['bytes_recorded'],
                                status['rem_nfs_storage_cap'],
                                status['rem_rpi_storage_cap'],
                                status['rpi_uptime(minutes)'],
                                hardware_id,
                                status['wr0_ss'],
                                status['wr0_lnk'],
                                  status['wr1_lnk'],
                                  status['wr0_tx'],
                                  status['wr0_rx'],
                                  status['wr1_tx'],
                                  status['wr1_rx'],
                                  status['wr0_setp'],
                                  status['wr0_mu'],
                                  status['wr0_crtt'],
                                  status['wr0_cko'],
                                  status['wr0_ucnt'],
                                  status['wr_temp'],
                                  status['wr_host'],
                                ))
            print("status: command executed")
            cur.execute(commands[1], (status['hardware_op_status'],hardware_id,))
            cur.execute(commands[2], (status['storage_op_status'],mount_id,))
            cur.execute(commands[3], (status['rpi_op_status'],hardware_id,))
            cur.execute(commands[4], (status['sdr_op_status'],hardware_id,))
            cur.execute(commands[5], (status['wr_op_status'],hardware_id,))
            # close the communication with the PostgreSQL server
            cur.close()
            conn.commit()
            print("Commands executed.")
            self.logger.write_log("INFO", "Status for %s updated in database"%(status['hostname']))
            os.remove(self.filename)
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            self.logger.write_log("ERROR", "Could not update status for %s in database"%(status['hostname']))
            # TODO: move file to a different location for inspection if an error occurs
            return
        finally:
            if conn is not None:
                conn.close()
                print("Database connection closed.")
