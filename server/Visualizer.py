# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

from Logger import Logger
import os
import numpy as np
import pandas as pd
import json
import scipy.io
import scipy.fftpack
import matplotlib.pyplot as plt
from matplotlib import cm
from datetime import datetime
from configparser import ConfigParser
import psycopg2

class Visualizer(object):
    def __init__(self):
        time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"]+"/logs/"
        self.logger = Logger("visualizer", log_path, "data_log-"+time+".log")
    
    def check_db(self):
        """Get list of recordings from the PostgreSQL database"""

        select = """
            SELECT file_name from recordings JOIN outputs ON recordings.recording_id = outputs.recording_id;
            """

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
            cur.execute(select)
            rows = cur.fetchall()
            file_list = []
            if rows is not None:
                for row in rows:
                    file_list.append(row[0])
                    #print(row)
            if not file_list:
                file_list.append("_")
            # close the communication with the PostgreSQL server
            cur.close()
            conn.commit()
            print("Command executed.")
            self.logger.write_log("INFO", "File names present in database collected")
            return file_list
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            self.logger.write_log("ERROR", "Could not grab file names from the database")
            return
        finally:
            if conn is not None:
                conn.close()
                print("Database connection closed.")
        
    def statistics(self, new_path):
        data = np.fromfile(new_path, dtype=np.int16)
        data = data/32768
        data = data[0::2] + 1j*data[1::2]
        try:
            self.mean_db = 10*np.log10(np.mean(np.abs(data)**2/50))
            self.max_db = 10*np.log10(np.max(np.abs(data)**2/50))
            self.median_db = 10*np.log10(np.median(np.abs(data)**2/50))
            self.standard_dev = np.std(np.abs(data))
            self.logger.write_log("INFO", "Average, Max, and Median Power calculated.")
        except Exception as e:
            self.logger.write_log("ERROR", "Failed to calculate average power")
        try:
            dataset = np.abs(data)**2
            m = len(dataset)
            s1 = np.sum(dataset)
            s2 = np.sum(dataset**2)
            k = m * (s2) / s1**2 - 1.0
            self.spec_kurtosis = k * (m + 1.0) / (m - 1.0)
            self.logger.write_log("INFO", "Kurtosis calculated.")
        except Exception as e:
            self.logger.write_log("ERROR", "Failed to calculate kurtosis: %s"%(repr(e)))

    def update_db(self, file_name):
        """Update tables in the PostgreSQL database"""

        select = """
            SELECT recording_id FROM recordings WHERE file_name = %s;
            """
        command ="""
            INSERT INTO outputs(recording_id, average_db, max_db, median_db, std_dev, kurtosis)
                VALUES(%s,%s,%s,%s,%s,%s)
                ON CONFLICT (recording_id) DO UPDATE SET recording_id=%s, average_db=%s, max_db=%s, median_db=%s, std_dev=%s, kurtosis=%s;
            """

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
            cur.execute(select, [file_name])
            print("visualizer: select executed")
            row = cur.fetchone()
            if row is not None:
                recording_id = row[0]
                cur.execute(command, (recording_id, self.mean_db, self.max_db, self.median_db, self.standard_dev, self.spec_kurtosis,recording_id, self.mean_db, self.max_db, self.median_db, self.standard_dev, self.spec_kurtosis,))
                print("visualizer: command executed")
            # close the communication with the PostgreSQL server
            cur.close()
            conn.commit()
            print("Command executed.")
            self.logger.write_log("INFO", "Statistics added to database")
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            self.logger.write_log("ERROR", "Could not add statistics for database recording id %s"%(recording_id))
            return
        finally:
            if conn is not None:
                conn.close()
                print("Database connection closed.")
