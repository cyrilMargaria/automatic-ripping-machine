#!/usr/bin/env python3

# set up logging

import os
import os.path
import logging
import logging.handlers
import sys
import time

from arm.config.config import cfg


def setuplogging(job, level=None):
    """Setup logging and return the logger. """
    # return a logger, so all logs are logged through a logger

    # Support different destination
    destination = cfg.get("LOGDEST", "FILE")
    log_level = cfg['LOGLEVEL']
    if level:
        log_level = level
    # normalize  cfg['LOGPATH'] (will be used only if destination is FILE
    logPath = cfg['LOGPATH']
    while logPath and logPath[-1] == "/":
        logPath = logPath[:-1]

    # setup helpful information for the log,
    # This isnt catching all of them
    # logbase is the log file name without the.log
    logbase = "empty"
    if job.label == "" or job.label is None:
        if job.disctype == "music":
            logbase =  job.identify_audio_cd()
    else:
        logbase = job.label
        # We need to give the logfile only to database
    # default to stdout
    log_handler = logging.StreamHandler(stream=sys.stdout)
    if destination == "FILE":        
        # Make the log dir if it doesnt exist
        if not os.path.exists(logPath):
            os.makedirs(logPath)
        # unique filename 
        if os.path.isfile(os.path.join(logPath, "{}.log".format(logbase))):
            # log already exist, generate an unique one
            logbase = str(job.label) + "_" + str(round(time.time() * 100))
        logfile = "{}.log".format(logbase)
        logfull = os.path.join(logPath, logfile)
        log_handler = logging.FileHandler(logfull)
    elif destination == "SYSLOG":
        log_handler = logging.handlers.SysLogHandler(address='/dev/log')
        # TODO: named pipe
        logfile = "/dev/null"
    elif destination.startswith("udp://"):
        destination = destination[len("udp://"):]
        tupl = destination.split(":")
        if len(tupl) > 1:
            tupl = (tupl[0], int(tupl[1]))
        else:
            tupl = (destination, 514)
        log_handler = logging.handlers.SysLogHandler(address=tupl)
        logfile = "/dev/null"
    elif destination.startswith("stdout"):
        # its already the case
        logfile = "1"        
        pass
    elif destination.startswith("stderr"):
        log_handler = logging.StreamHandler(stream=sys.stderr)
        logfile = "2"        
    else:
        # suppose a file
        log_handler = logging.FileHandler(destination)
        logfile = "destination"

    fmt = '[%(asctime)s] %(levelname)s ARM[{}]: %(message)s'.format(logbase)
    if log_level == "DEBUG":
        fmt = '[%(asctime)s] %(levelname)s ARM[{}]: %(module)s.%(funcName)s %(message)s'.format(logbase)

    
    job.logfile = logfile
    logging.basicConfig(format=fmt, handlers=[log_handler], datefmt='%Y-%m-%d %H:%M:%S', level=log_level)
    result = logging.getLogger("arm")
    # This stops apprise spitting our secret keys when users posts online
    logging.getLogger("apprise").setLevel(logging.WARN)
    logging.getLogger("requests").setLevel(logging.WARN)
    logging.getLogger("urllib3").setLevel(logging.WARN)

    # Return the full logfile location to the logs
    return logfile


def clean_up_logs(logpath, loglife):
    """Delete all log files older than x days\n
    logpath = path of log files\n
    loglife = days to let logs live\n

    """
    if loglife < 1:
        logging.info("loglife is set to 0. Removal of logs is disabled")
        return False
    now = time.time()
    logging.info(f"Looking for log files older than {loglife} days old.")
    if not os.path.exists(logpath):
        return
    for filename in os.listdir(logpath):
        fullname = os.path.join(logpath, filename)
        if fullname.endswith(".log") and os.stat(fullname).st_mtime < now - loglife * 86400:
            logging.info(f"Deleting log file: {filename}")
            os.remove(fullname)
