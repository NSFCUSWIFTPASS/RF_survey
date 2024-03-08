# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben, Cole Forrester.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import os
import glob
import psycopg2
import re
import shutil
import json
import time
from datetime import datetime
from configparser import ConfigParser
from Logger import Logger

class Update(object):
    def __init__(self, path):
        time = datetime.now().strftime("%Y-%m-%d")
        log_path = os.environ["HOME"]+"/logs/"
        self.logger = Logger("UPDATE DB", log_path, "db_log-"+time+".log")
        self.path = path

        repl = {"-": "", " ": "T", ".": "M", ":": ""}
        self.rep = dict((re.escape(k), v) for k, v in repl.items())
        self.pattern = re.compile("|".join(self.rep.keys()))

        self.conn = None
        try:
            # read connection parameters
            parser = ConfigParser()
            # read config file
            parser.read("/home/nrdz/HCRO/server/database.ini")

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
            self.conn = psycopg2.connect(**db)
            print("Connection successful.")
            self.logger.write_log("INFO", "Database Connection successful.")
            # create a cursor
            self.cur = self.conn.cursor()
        except (Exception) as e:
            self.logger.write_log("ERROR", "Failed to connect to database: %s"%(repr(e)))
            return      

    def run(self, meta_list, data_list):
        print(meta_list)
        print(data_list)
        select = """
            SELECT hardware_id FROM rpi WHERE hostname = %s;
            """
    
        commands =(
            """
            INSERT INTO metadata(frequency, sample_rate, bandwidth, gain, length, interval, bit_depth)
                VALUES(%s,%s,%s,%s,%s,%s,%s) 
            ON CONFLICT (frequency, sample_rate, bandwidth, gain, length, interval, bit_depth) DO UPDATE SET frequency=%s, sample_rate=%s, bandwidth=%s, gain=%s, length=%s, interval=%s, bit_depth=%s
            RETURNING metadata_id;
            """,
            """
            INSERT INTO outputs(hardware_id, metadata_id, created_at, average_db, max_db, median_db, std_dev, kurtosis) 
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s);
            """,
            """
            SELECT outputs.created_at
            FROM outputs
            INNER JOIN hardware on hardware.hardware_id = outputs.hardware_id
            INNER JOIN rpi on rpi.hardware_id = hardware.hardware_id
            INNER JOIN metadata on metadata.metadata_id = outputs.metadata_id
            WHERE metadata.metadata_id = %s and rpi.hostname = %s and DATE_TRUNC('hour', TO_TIMESTAMP(%s, 'YYYY-MM-DD HH24:MI:SS')) < outputs.created_at
            ORDER BY (outputs.max_db - average_db*(1+(SQRT(outputs.std_dev)*outputs.kurtosis))) DESC LIMIT(1);
            """,
            """
            SELECT outputs.created_at
            FROM outputs
            INNER JOIN hardware on hardware.hardware_id = outputs.hardware_id
            INNER JOIN rpi on rpi.hardware_id = hardware.hardware_id
            INNER JOIN metadata on metadata.metadata_id = outputs.metadata_id
            WHERE metadata.metadata_id = %s and rpi.hostname = %s and DATE_TRUNC('hour', TO_TIMESTAMP(%s, 'YYYY-MM-DD HH24:MI:SS')) < outputs.created_at
            ORDER BY (0.5*outputs.average_db+0.5*outputs.median_db) ASC LIMIT(1);
            """
            )

        try:
            lq_dict = {'loudest': {}, 'quietest': {}}
            upload_count = 0
            for index, row in data_list.iterrows():
                print("timestamp")
                print(row['timestamp'])
                self.cur.execute(select, [row['hostname']])
                hardware_fetch = self.cur.fetchone()
                if hardware_fetch is not None:
                    hardware_id = hardware_fetch[0]
                else:
                    self.cur.close()
                    self.logger.write_log("ERROR", "No hardware_id found for this hostname: %s"%(row['hostname']))
                    return
                self.logger.write_log("INFO", "Select finished, recieved hardware_id: %s" % (hardware_id))
                self.cur.execute(commands[0], (
                                    meta_list.iloc[[row['meta_index']]]['frequency'].item(),
                                    meta_list.iloc[[row['meta_index']]]['sampling_rate'].item(),
                                    meta_list.iloc[[row['meta_index']]]['sampling_rate'].item(),
                                    meta_list.iloc[[row['meta_index']]]['gain'].item(),
                                    meta_list.iloc[[row['meta_index']]]['length'].item(),
                                    meta_list.iloc[[row['meta_index']]]['interval'].item(),
                                    meta_list.iloc[[row['meta_index']]]['bit_depth'].item(),
                                    meta_list.iloc[[row['meta_index']]]['frequency'].item(),
                                    meta_list.iloc[[row['meta_index']]]['sampling_rate'].item(),
                                    meta_list.iloc[[row['meta_index']]]['sampling_rate'].item(),
                                    meta_list.iloc[[row['meta_index']]]['gain'].item(),
                                    meta_list.iloc[[row['meta_index']]]['length'].item(),
                                    meta_list.iloc[[row['meta_index']]]['interval'].item(),
                                    meta_list.iloc[[row['meta_index']]]['bit_depth'].item(),
                                    ))
                print("First insert finished, received metadata_id")
                metadata_id = self.cur.fetchone()[0]
                print(metadata_id)
                self.logger.write_log("INFO", "Metadata updated with metadata_id: %s"%(metadata_id))
                self.cur.execute(commands[1], (hardware_id, 
                    metadata_id, 
                    row['timestamp'], 
                    row['average'], 
                    row['max'], 
                    row['median'], 
                    row['std'], 
                    row['kurtosis'],
                    ))
                upload_count += 1
                # check if any of the added data was the loudest or quietest over the last hour
                loudest = ""
                quietest = ""
                print(self.cur.mogrify(commands[2], (metadata_id, row['hostname'], row['timestamp'],)))
                self.cur.execute(commands[2], (metadata_id, row['hostname'], row['timestamp'],))
                loudest_fetch = self.cur.fetchone()
                if loudest_fetch is not None:
                    loudest = loudest_fetch[0]
                    print("loudest fetch is not none")
                else:
                    loudest = row['timestamp']
                    print("loudest fetch is none")
                self.cur.execute(commands[3], (metadata_id, row['hostname'], row['timestamp'],))
                quietest_fetch = self.cur.fetchone()
                if quietest_fetch is not None:
                    quietest = quietest_fetch[0]
                    print("quietest fetch is not none")
                else:
                    quietest = row['timestamp']
                    print("quietest fetch is none")
                #print("loudest")
                #print(loudest)
                #print("quietest")
                #print(quietest)

                if metadata_id in lq_dict['loudest'].keys():
                    lq_dict['loudest'][metadata_id].update({row['hostname']: loudest})
                else:
                    lq_dict['loudest'].update({metadata_id: {row['hostname']: loudest}})

                if metadata_id in lq_dict['quietest'].keys():
                    lq_dict['quietest'][metadata_id].update({row['hostname']: quietest})
                else:
                    lq_dict['quietest'].update({metadata_id: {row['hostname']: quietest}})
                
                self.logger.write_log("INFO", "Outputs for %s with timestamp %s added to the Database"%(row['hostname'], row['timestamp']))

            # close the communication with the PostgreSQL server
            self.cur.close()
            self.conn.commit()
            self.logger.write_log("INFO", "Upload count: %s"%(upload_count))
            return lq_dict
        except (Exception, psycopg2.DatabaseError) as error:
            self.logger.write_log("ERROR", "Failed to write to database: %s"%(repr(error)))
            return
        finally:
            if self.conn is not None:
                self.conn.close()
                self.logger.write_log("INFO", "Database connection closed.")

    def lq_cleanup(self, file_path):
        
        try:
            file_list = glob.glob(file_path+"*.sc16")
            for file_ in file_list:
                #self.logger.write_log("DEBUG", "Evaluating %s"%(file_.split('/')[-1]))
                if os.path.exists(file_) and os.path.exists(file_.replace(".sc16", ".json")):
                    #self.logger.write_log("INFO", "No excess files detected")
                    continue
                else:
                    os.remove(file_)
                    self.logger.write_log("INFO", "Removed %s due to lack of corresponding metadata file"%(file_.split('/')[-1]))
        except Exception as error:
            self.logger.write_log("ERROR", "Failed to remove excess data files: %s"%(repr(error)))

    def process_lq(self, file_list, storage_path, lq_dict):

        #print(lq_dict)
    
        file_list = [fi for fi in file_list if not fi.endswith("status.json")]
        
        try:
            for lq, values in lq_dict.items():
                for meta_index, value in values.items():
                    for host, stat in value.items():
                        #print("%s: %s"%(host, stat))
                        stat = stat.strftime("%Y-%m-%d %H:%M:%S.%f")
                        timestamp = self.pattern.sub(lambda m: self.rep[re.escape(m.group(0))], stat)
                        #print(timestamp)
                        file_ = [i for i in file_list if timestamp in i]
                        #print(file_)
                        if file_:

                            current_year = timestamp[0:4]
                            current_month = timestamp[4:6]
                            current_day = timestamp[6:8]
                            current_hour = timestamp[9:11]

                            path = storage_path+"/"+current_year+"/"+current_month+"/"+current_day+"/"+current_hour+"/"+lq+"/"
                            #print(path)

                            if not os.path.exists(path):
                                os.makedirs(os.path.dirname(path), exist_ok=True)

                            for f in file_:
                                if f.endswith(".json"):
                                    new_metadata = f

                            with open(new_metadata) as f:
                                metadata_a = dict(json.load(f).items())

                            metalist_a = [metadata_a['hostname'], metadata_a['frequency'], metadata_a['interval'],
                                    metadata_a['length'], metadata_a['gain'], metadata_a['sampling_rate']]
                            #print("metalist_a: %s"%(metalist_a))

                            current = glob.glob(path+"*"+host+"*.json")
                            #print("current: %s"%(current))

                            if current:
                                for c in current:
                                    with open(c) as f:
                                        metadata_b = dict(json.load(f).items())
                                    metalist_b = [metadata_b['hostname'], metadata_b['frequency'], metadata_b['interval'], 
                                        metadata_b['length'], metadata_b['gain'], metadata_b['sampling_rate']]
                                    #print("metalist_b: %s"%(metalist_b))
                                    if metalist_a == metalist_b:
                                        os.remove(c)
                                        self.logger.write_log("DEBUG", "Removed: %s"%(c))
                                        os.remove(c.replace(".json", ".sc16"))
                                        self.logger.write_log("DEBUG", "Removed: %s"%(c.replace(".json", ".sc16")))
                                        time.sleep(1)
                                        if os.path.exists(c.replace(".json", ".sc16")):
                                            os.unlink(c.replace(".json", ".sc16"))
                                        #print("removed %s"%(c))

                            for file_name in file_:
                                #print(file_name)
                                #print("%s%s"%(path,file_name.split('/')[-1]))
                                copy = shutil.copy(file_name, '%s%s'%(path, file_name.split('/')[-1]))
                                print("Copied: %s"%(copy))

                            self.logger.write_log("INFO", "Files successfully moved to the %s Directory: %s"%(lq, os.path.basename(file_name)))
                        
                            self.lq_cleanup(path)

        except Exception as error:
            self.logger.write_log("ERROR", "Failed to copy files: %s"%(repr(error)))
    
    def cleanup(self, file_list):
        
        try:
            for file_ in file_list:
                data_file = file_[1]
                meta_file = data_file.replace(".sc16", ".json")
                if os.path.exists(data_file) and os.path.exists(meta_file):
                    os.remove(data_file)
                    os.remove(meta_file)
                    #shutil.move(meta_file, "/home/nrdz/test_data/"+meta_file.split('/')[-1])
            self.logger.write_log("INFO", "Files deleted from the Data Dump Directory")
        except Exception as error:
            self.logger.write_log("ERROR", "Failed to remove files: %s"%(repr(error)))
