# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import os
import shutil
import json
import psycopg2
import numpy as np
from configparser import ConfigParser
from Logger import Logger
from datetime import datetime

class Organizer(object):
    def __init__(self, filename):
        self.filename = filename
        self.path = os.path.dirname(self.filename)+"/"
        self.name = os.path.splitext(os.path.basename(self.filename))[0]
        self.meta_data = os.path.basename(self.filename)
        self.iq_data = os.path.splitext(os.path.basename(self.filename))[0]+".sc16"
        self.timestamp = self.name[-22:-18]+"-"+self.name[-18:-16]+"-"+self.name[-16:-14]+" "+self.name[-13:-11]+":"+self.name[-11:-9]+":"+self.name[-9:-7]+"."+self.name[-6:]
        self.time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"]+"/logs/"
        self.logger = Logger("organizer", log_path,"data_log-"+self.time+".log")      

    def read_json(self):
        with open(self.path+self.meta_data) as f:
            data = dict(json.load(f).items())
        frequency = str(int(int(data['frequency'])/1e6))
        bandwidth = str(int(int(data['sampling_rate'])/1e6))
        self.group = data['group']
        self.new_path = "/data/"+data['organization']+"/"+data['gcs']+"/"+data['hostname']+"/"+data['serial']+"/"+frequency+"/"+bandwidth+"/"+str(data['interval'])+"/"+str(data['length'])+"/"
        return self.new_path

    def move_file(self, new_path):
        if not os.path.exists(new_path):
            try:
                os.makedirs(new_path)
            except Exception as e:
                self.logger.write_log("ERROR", "Error when creating directory: %s"%(repr(e)))
                return
        try:
            shutil.move(self.path+self.iq_data, new_path+self.iq_data)
            shutil.move(self.path+self.meta_data, new_path+self.meta_data)
            self.logger.write_log("INFO", "%s moved successfully" % (self.name))
        except Exception as e:
            self.logger.write_log("ERROR", "Moving "+self.name+" failed. Cause: %s"%(repr(e)))
            return
    
    def update_db(self, new_path):
        """Update tables in the PostgreSQL database"""
        with open(new_path+self.meta_data) as f:
                configs = dict(json.load(f).items())

        select = """
            SELECT hardware_id FROM rpi WHERE hostname = %s;
            """
        
        commands =(
            """
            INSERT INTO metadata(org, frequency, sample_rate, bandwidth, gain, length, interval, bit_depth)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (org, frequency, sample_rate, bandwidth, gain, length, interval, bit_depth) DO UPDATE SET org=%s, frequency=%s, sample_rate=%s, bandwidth=%s, gain=%s, length=%s, interval=%s, bit_depth=%s
                RETURNING metadata_id;
            """,
            """
            INSERT INTO recordings(hardware_id, metadata_id, file_name, file_path, survey_id, created_at) 
                VALUES(%s,%s,%s,%s,%s,%s)
                ON CONFLICT (file_name) DO UPDATE 
                SET hardware_id=%s, metadata_id=%s, file_name=%s, file_path=%s, survey_id=%s, created_at=%s;
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
            cur.execute(select, [configs['hostname']])
            print("organizer: select executed")
            row = cur.fetchone()
            if row is not None:
                hardware_id = row[0]
                print(row[0])
            else:
                cur.close()
                return
            cur.execute(commands[0], (configs['organization'],
                                configs['frequency'],
                                configs['sampling_rate'],
                                configs['sampling_rate'],
                                configs['gain'],
                                configs['length'],
                                configs['interval'],
                                configs['bit_depth'],
                                configs['organization'],
                                configs['frequency'],
                                configs['sampling_rate'],
                                configs['sampling_rate'],
                                configs['gain'],
                                configs['length'],
                                configs['interval'],
                                configs['bit_depth'],
                                ))
            metadata_id = cur.fetchone()
            print("organizer: command 1 executed")
            cur.execute(commands[1], (hardware_id, metadata_id, self.name, self.new_path, self.group, self.timestamp,hardware_id, metadata_id, self.name, self.new_path, self.group, self.timestamp,))
            print("organizer: command 2 executed")
            # close the communication with the PostgreSQL server
            cur.close()
            conn.commit()
            print("Commands executed.")
            self.logger.write_log("INFO", "Metadata and recording information added to database")
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            self.logger.write_log("ERROR", "Could not add metadata or recording information for  %s to database"%(configs['hostname']))
            return
        finally:
            if conn is not None:
                conn.close()
                print("Database connection closed.")
