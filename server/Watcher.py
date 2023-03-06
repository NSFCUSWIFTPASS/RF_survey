# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

import time
import os
import glob
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from multiprocessing import Process
from Logger import Logger
from Organizer import Organizer
from Visualizer import Visualizer
from GracefulKiller import GracefulKiller
from Status import Status
from Hardware import Hardware

class Watcher(FileSystemEventHandler):
    def __init__(self, logger, path, pattern):
        self.logger = logger
        self.path_to_watch = path
        self.pattern = pattern
        
    ####################################################################################
    # Modifies the FileSystemEventHandler's on_modified function                       #
    # Since this event occurs whenever a modification event is reported by the system  #
    # it's safer to wait for a second before doing anything to let the system          #
    # finish writing. Each JSON file is 257 bytes, 1 second is enough.                 #
    ####################################################################################

    def on_modified(self, event):
        
        time.sleep(2)
        # get a list of json files in the data directory
        hardware_list = glob.glob(self.path_to_watch+"/*hardware.json")
        for new_hardware in hardware_list:   
            self.logger.write_log("INFO","Attempting to add new hardware to database")
            try:
                # instantiates the Organizer class - passing the JSON file here makes it possible to use it for later functions
                hardware_update = Hardware(new_hardware)
            except Exception as e:
                self.logger.write_log("ERROR", "Failed to parse hardware update from %s"%(new_hardware))
            # reads the JSON and returns a file path created using the information provided in the JSON
            hardware_update.update_db()
        
        status_list = glob.glob(self.path_to_watch+"/*status.json")
        for update in status_list:   
            self.logger.write_log("INFO","Attempting to write new status to database")
            try:
                # instantiates the Organizer class - passing the JSON file here makes it possible to use it for later functions
                status_update = Status(update)
            except Exception as e:
                self.logger.write_log("ERROR", "Failed to parse status update from %s"%(update))
            # reads the JSON and returns a file path created using the information provided in the JSON
            status_update.update_db()
        
        
        file_list = sorted(glob.glob(self.path_to_watch+"/*M??????"+self.pattern)) ### pattern needs to be changed
        global new_paths
        new_paths = []
        for metadata in file_list:
            
            self.logger.write_log("INFO","Moving of %s started."%(os.path.splitext(os.path.basename(metadata))[0]))
            try:
                # instantiates the Organizer class - passing the JSON file here makes it possible to use it for later functions
                organize = Organizer(metadata)
            except Exception as e:
                self.logger.write_log("ERROR", "Starting file organization failed with: %s"%(repr(e)))
            # reads the JSON and returns a file path created using the information provided in the JSON
            new_path = organize.read_json()
            file_path, file_name = os.path.split(metadata)
            new_paths.append(new_path+file_name)
            data = metadata.replace(".json",".sc16")
            organize.move_file(new_path)
            organize.update_db(new_path)
            
            self.logger.write_log("INFO","Moving of %s finished."%(os.path.splitext(os.path.basename(metadata))[0]))
        return 
               

class Crawler(FileSystemEventHandler):
    def __init__(self, logger, path, suffix_meta=".json", suffix_data=".sc16", suffix_out=".jpg"):
        self.logger = logger
        self.directory = path
        self.suffix_meta = suffix_meta
        self.suffix_data = suffix_data
        self.suffix_out = suffix_out

    ####################################################################################
    # Modifies the FileSystemEventHandler's on_modified function                       #
    # Since this event occurs whenever a modification event is reported by the system  #
    # it's safer to wait for a second before doing anything to let the system          #
    # finish writing. Each JSON file is 257 bytes, 1 second is enough.                 #
    ####################################################################################

    def on_modified(self, event):
        time.sleep(10)
        # get a list of json files in the data directory
        for metadata in sorted(glob.iglob(self.directory+"/**/*.json", recursive=True)):
            file_path, file_name = os.path.split(metadata)
            name = os.path.splitext(file_name)[0]
            #print(name)
            visuals = Visualizer()
            processed = visuals.check_db()
            if name not in processed:
                #if the data hasn't been processed yet:
                self.logger.write_log("INFO","Processing of %s started."%(os.path.splitext(os.path.basename(metadata))[0]))
                data = metadata.replace(self.suffix_meta,self.suffix_data)
                #print(data)
                visuals.statistics(data)
                visuals.update_db(name)
                self.logger.write_log("INFO","Processing of %s finished."%(os.path.splitext(os.path.basename(metadata))[0]))

if __name__ == '__main__':
    log_time = datetime.now().strftime("%Y-%m-%d")
    log_path = os.environ["HOME"]+"/logs/"
    logger = Logger("watcher", log_path, "data_log-"+log_time+".log")
    grace = GracefulKiller()
    with open(os.environ["HOME"]+"/watcher.pid","w") as f:
        f.write(str(os.getpid()))

    PATH_TO_WATCH = "/sync"
    PATH_TO_PROCESS = "/data/University_of_Colorado_Testbed/40.0136N105.2521W/ucb-rpi-043/323E386" #"/data" 
    WATCH_DELAY = 10
    WATCH_PATTERN = ".json" # only look for JSON files since they are created AFTER the IQ data file

    file_event_handler = Watcher(logger, PATH_TO_WATCH, WATCH_PATTERN)
    file_observer = Observer()
    file_observer.schedule(file_event_handler, PATH_TO_WATCH, recursive=False)
    file_observer.start()
    
    out_event_handler = Crawler(logger, PATH_TO_PROCESS)
    out_observer = Observer()
    out_observer.schedule(out_event_handler, PATH_TO_PROCESS, recursive=True)
    out_observer.start()

    try:
        while True and not grace.kill_now:
            # do not check the directory constantly, wait x seconds between each check
            time.sleep(WATCH_DELAY)
    except Exception as e:
        file_observer.stop()
        out_observer.stop()
        file_observer.join()
        out_observer.join()
