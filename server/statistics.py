import time
import os
from datetime import datetime
from Logger import Logger
from Visualizer import Visualizer
from GracefulKiller import GracefulKiller

def main(logger, directory, grace, suffix_meta=".json", suffix_data=".sc16"):

    try:
        while True and not grace.kill_now:
            time.sleep(1)
            # get a list of json files in the data directory
            visuals = Visualizer()
            processed = visuals.check_db()
            print(processed[0])
            print("walking directory")
            for path, dirlist, filelist in os.walk(directory, topdown=True):
                files = [ fi for fi in filelist if fi.endswith(".json") ]
                for metadata in files:
                    #print(path+"/"+metadata)
                    file = os.path.splitext(metadata)[0]
                    #print(file)
                    if file not in processed:
                        #if the data hasn't been processed yet:
                        logger.write_log("INFO","Processing of %s started."%(os.path.splitext(os.path.basename(metadata))[0]))
                        data = metadata.replace(suffix_meta,suffix_data)
                        print(data)
                        visuals.statistics(path+"/"+data)
                        visuals.update_db(file)
                        logger.write_log("INFO","Processing of %s finished."%(os.path.splitext(os.path.basename(metadata))[0]))
                        os.remove(path+"/"+data)
                        os.remove(path+"/"+metadata)
    except Exception as e:
        logger.write_log("DEBUG","Aborted: %s"%(repr(e)))

if __name__ == '__main__':
    log_time = datetime.now().strftime("%Y-%m-%d")
    log_path = os.environ["HOME"]+"/logs/"
    logger = Logger("statistics", log_path, "stats_log-"+log_time+".log")
    grace = GracefulKiller()
    with open(os.environ["HOME"]+"/stats.pid","w") as f:
        f.write(str(os.getpid()))

    PATH_TO_PROCESS = "/data"
    WATCH_PATTERN = ".json"

    main(logger, PATH_TO_PROCESS, grace)
