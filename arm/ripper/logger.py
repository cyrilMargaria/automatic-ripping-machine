#!/usr/bin/env python3

# set up logging

import os
import os.path
import logging
import logging.handlers
import sys
import time
import threading
import atexit
import time
import random
import string
from arm.config.config import cfg

def random_pipe(directory, idlen=8):
    """ Create a randomly named pipe """
    retries = 20
    while retries > 0:
        retries -= 1
        random_name = os.path.join(directory, "".join([random.choice(string.ascii_letters+string.digits) for x in range(0, idlen)]))
        if not os.path.exists(random_name):
            os.mkfifo(random_name)
            return random_name
    raise ValueError("could not create randome FIFO")


class redirectFile(threading.Thread):
    """ read a pipe and log it to a logger (function) """
    def __init__(self, logf, pipe):
        super().__init__()
        self._logger = logf
        self._pipename = pipe
        self._pipe = None
        self._stop = threading.Event()
        self._running = False
        self.setDaemon(True)
        self.setName(f"Log piper for {pipe}")
        atexit.register(self._finish)
        
    def _finish(self):
        if self._pipe:
            self._pipe.close()
        if self._running:
            self._stop.set()
        try:
            if self._pipename:
                os.remove(self._pipename)
        except:
            pass

        
    def run(self):
        try:
            self._stop.clear()
            self._running = True
            self._pipe = open(self._pipename, "r")
            while not self._stop.is_set():
                line = self._pipe.readline()
                if line:
                    self._logger(line.strip())
                else:
                    self._stop.wait(1)
        except Exception as e:
            self._running = False
            self._logger("Exception in redirectFile thread: %s",e)
            

def setup_py_logging(logbase, level=None, unique=False):
    """ 
     Setup python logging handlers based on the configuration
      - logbase: job/subsystem we are logging for
      - level: optional command-line log level
      - unique: For file, If an existing file exist. create and unique log file name 
      return has_file, logfile, pipe:
        - has_file is true if one logger is to a file,
        - logfile is the full path to the log file 
        - pipe set to True if a named pipe must be created for helpers programs
    """
    
    # Support different destination
    destination = cfg.get("LOGDEST", "FILE")
    log_level = cfg.get('LOGLEVEL', 'INFO')
    if level:
        log_level = level
    # normalize  cfg['LOGPATH'] (will be used only if destination is FILE
    log_path = cfg['LOGPATH']
    while log_path and log_path[-1] == "/":
        log_path = log_path[:-1]
    #
    logfile = None
    log_handlers = []
    #  if pipe is set to True, a named pipe will be created
    # and used for the other programs to redirect their log to
    pipe = False
    # if a real file is provided, use it
    has_file = False
    for dst in destination.split(","):
        dst = dst.strip()
        log_handler = None
        if dst.upper() == "FILE":
            print("Use file")
            # Make the log dir if it doesnt exist
            if not os.path.exists(log_path):
                os.makedirs(log_path)
            # unique filename
            if unique and os.path.isfile(os.path.join(log_path, "{}.log".format(logbase))):
                # log already exist, generate an unique one
                logbase = logbase + "_" + str(round(time.time() * 100))
            logfile = "{}.log".format(logbase)
            logfull = os.path.join(log_path, logfile)
            logfile = logfull
            log_handler = logging.FileHandler(logfull)
            has_file = True
        elif dst.upper() == "SYSLOG":
            log_handler = logging.handlers.SysLogHandler(address='/dev/log')
            pipe = True
        elif dst.startswith("udp://"):
            dst = dst[len("udp://"):]
            tupl = dst.split(":")
            if len(tupl) > 1:
                tupl = (tupl[0], int(tupl[1]))
            else:
                tupl = (dst, 514)
            log_handler = logging.handlers.SysLogHandler(address=tupl)
            pipe = True
        elif dst.startswith("stdout"):
            print("Use Stdout")
            log_handler = logging.StreamHandler(stream=sys.stdout)
            pipe = True
        elif dst.startswith("stderr"):
            log_handler = logging.StreamHandler(stream=sys.stderr)
            pipe = True
        else:
            # suppose a file
            log_handler = logging.FileHandler(dst)
            logfile = dst
            has_file = True
        if log_handler:
            log_handlers.append(log_handler)
    if not log_handlers:
        log_handlers = [logging.StreamHandler(stream=sys.stdout)]
    level = getattr(logging, log_level.upper())
    fmt = '[%(asctime)s] %(levelname)s ARM[{}]: %(message)s'.format(logbase)
    if log_level == "DEBUG":
        fmt = '[%(asctime)s] %(levelname)s ARM[{}]: %(module)s.%(funcName)s %(message)s'.format(logbase)
    # force existing logger to be removed, otherwise we do not log
    logging.basicConfig(format=fmt, handlers=log_handlers, force=True, datefmt='%Y-%m-%d %H:%M:%S', level=level)
    return has_file, logfile, pipe

            
def setuplogging(job, level=None):
    """Setup logging and return the logger. """
    # setup helpful information for the log,
    # This isnt catching all of them
    # logbase is the log file name without the.log
    logbase = "empty"
    if job.label == "" or job.label is None:
        if job.disctype == "music":
            logbase = job.identify_audio_cd()
    else:
        logbase = job.label
        # We need to give the logfile only to database
    has_file, logfile, pipe = setup_py_logging(logbase, level=level, unique=True)

    if pipe and not has_file:
        logger = logging.getLogger("arm")
        # Make it configurable if needed
        localpipe = random_pipe("/tmp")
        logfile = localpipe
        logger.info("Local pipe %s will be used for log redirection", localpipe)
        r = redirectFile(logger.debug, localpipe)
        r.start()
    job.logfile = logfile
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
