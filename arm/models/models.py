import os
import subprocess
import pyudev
import psutil
import logging
import time
import json
import os.path

from arm.ripper import music_brainz
from arm.db import db
from arm.config.config import cfg
from flask_login import LoginManager, current_user, login_user, UserMixin  # noqa: F401
from prettytable import PrettyTable
import platform
hidden_attribs = ("OMDB_API_KEY", "EMBY_USERID", "EMBY_PASSWORD", "EMBY_API_KEY", "PB_KEY", "IFTTT_KEY", "PO_KEY",
                  "PO_USER_KEY", "PO_APP_KEY", "ARM_API_KEY", "TMDB_API_KEY")
HIDDEN_VALUE = "<hidden>"
import platform
from arm.ripper import fs_utils

logger = logging.getLogger("arm")

class Job(db.Model):
    job_id = db.Column(db.Integer, primary_key=True)
    arm_version = db.Column(db.String(20))
    crc_id = db.Column(db.String(63))
    logfile = db.Column(db.String(256))
    start_time = db.Column(db.DateTime)
    stop_time = db.Column(db.DateTime)
    job_length = db.Column(db.String(12))
    status = db.Column(db.String(32))
    stage = db.Column(db.String(63))
    no_of_titles = db.Column(db.Integer)
    title = db.Column(db.String(256))
    title_auto = db.Column(db.String(256))
    title_manual = db.Column(db.String(256))
    year = db.Column(db.String(4))
    year_auto = db.Column(db.String(4))
    year_manual = db.Column(db.String(4))
    video_type = db.Column(db.String(20))
    video_type_auto = db.Column(db.String(20))
    video_type_manual = db.Column(db.String(20))
    imdb_id = db.Column(db.String(15))
    imdb_id_auto = db.Column(db.String(15))
    imdb_id_manual = db.Column(db.String(15))
    poster_url = db.Column(db.String(256))
    poster_url_auto = db.Column(db.String(256))
    poster_url_manual = db.Column(db.String(256))
    devpath = db.Column(db.String(15))
    # Some OS have the title in it, 
    mountpoint = db.Column(db.String(256))
    hasnicetitle = db.Column(db.Boolean)
    errors = db.Column(db.Text)
    disctype = db.Column(db.String(20))  # dvd/bluray/data/music/unknown
    label = db.Column(db.String(256))
    path = db.Column(db.String(256))
    ejected = db.Column(db.Boolean)
    updated = db.Column(db.Boolean)
    pid = db.Column(db.Integer)
    pid_hash = db.Column(db.Integer)
    tracks = db.relationship('Track', backref='job', lazy='dynamic')
    config = db.relationship('Config', uselist=False, backref="job")
    host = db.Column(db.String(256))

    def __init__(self, devpath):
        """Return a disc object"""
        self.devpath = devpath
        self.label = ""
        self.hasnicetitle = False
        self.video_type = "unknown"
        self.ejected = False
        self.updated = False
        self.logger = None
        self.host = platform.node()
        if cfg['VIDEOTYPE'] != "auto":
            self.video_type = cfg['VIDEOTYPE']
        self.mountpoint, self.label, self.disctype = fs_utils.get_device_info(self.devpath)
        if not self.mountpoint:
            raise ValueError("No mount point")
        self.get_pid()        
        if self.disctype == "dvd" and not self.label:
            logging.info("No disk label Available. Trying lsdvd")
            command = f"lsdvd {devpath} | grep 'Disc Title' | cut -d ' ' -f 3-"
            lsdvdlbl = str(subprocess.check_output(command, shell=True).strip(), 'utf-8')
            self.label = lsdvdlbl    

    def get_pid(self):
        """ return current pid """
        pid = os.getpid()
        #proc = psutil.Process(pid)
        self.pid = pid
        # why do we care? 
        self.pid_hash = 0

    def get_disc_type(self, found_hvdvd_ts):
        if self.disctype == "music":
            logging.debug("Disc is music.")
            # need to unmount it
            fs_utils.unmount_device(self.devpath)
            self.label = music_brainz.main(self)
        elif os.path.isdir(self.mountpoint + "/VIDEO_TS"):
            logging.debug(f"Found: {self.mountpoint}/VIDEO_TS")
            self.disctype = "dvd"
        elif os.path.isdir(self.mountpoint + "/video_ts"):
            logging.debug(f"Found: {self.mountpoint}/video_ts")
            self.disctype = "dvd"
        elif os.path.isdir(self.mountpoint + "/BDMV"):
            logging.debug(f"Found: {self.mountpoint}/BDMV")
            self.disctype = "bluray"
        elif os.path.isdir(self.mountpoint + "/HVDVD_TS"):
            logging.debug(f"Found: {self.mountpoint}/HVDVD_TS")
            # do something here
        elif found_hvdvd_ts:
            logging.debug("Found file: HVDVD_TS")
            # do something here too
        else:
            logging.debug("Did not find valid dvd/bd files. Changing disctype to 'data'")
            self.disctype = "data"
            self.title_auto = f"Data-{self.label}"
            self.year_auto = ""

    def identify_audio_cd(self):
        """
        Get the title for audio cds to use for the logfile name.

        Needs the job class passed into it so it can be forwarded to mb

        return - only the logfile - setup_logging() adds the full path
        """
        # Use the music label if we can find it - defaults to music_cd.log
        disc_id = music_brainz.get_disc_id(self)
        mb_title = music_brainz.get_title(disc_id, self)
        if mb_title == "not identified":
            self.label = self.title = "not identified"
            logfile = "music_cd"
        else:
            logfile = mb_title
        return logfile

    def __str__(self):
        """Returns a string of the object"""
        result = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            result = result + "(" + str(attr) + "=" + str(value) + ") "
        return result

    def pretty_table(self):
        """Returns a string of the prettytable"""
        x = PrettyTable()
        x.field_names = ["Config", "Value"]
        x._max_width = {"Config": 50, "Value": 60}
        for attr, value in self.__dict__.items():
            if attr == "config":
                x.add_row([str(attr), str(value.pretty_table())])
            else:
                x.add_row([str(attr), str(value)])
        return str(x.get_string())

    def get_d(self):
        r = {}
        for key, value in self.__dict__.items():
            if '_sa_instance_state' not in key:
                r[str(key)] = str(value)
        return r

    def __repr__(self):
        return '<Job {}>'.format(self.label)

    def eject(self):
        """Eject disc if it hasn't previously been ejected"""
        self.ejected = bool(fs_utils.eject_device(self.devpath))

    def write_metadata(self, destination):
        """ Write metadata to file and to the file(s) themselves"""
        try:
            f = open(os.path.join(destination, "metadata.json"), "w")
            metadata = {}
            # filter selected attribute and only set attribute with value
            for att in ["no_of_titles", "title", "title_auto", "title_manual",
                        "year", "year_auto", "year_manual", "video_type", "video_type_auto",
                        "video_type_manual", "imdb_id", "imdb_id_auto", "imdb_id_manual",
                        "poster_url", "poster_url_auto", "poster_url_manual",
                        "label", "crc_id", "disctype"]:
                data = getattr(self, att)
                if data:
                    metadata[att] = data
            json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning("Could not write %s metadata: %s", self.label, e)


class Track(db.Model):
    """ represents a track """
    track_id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.job_id'))
    track_number = db.Column(db.String(4))
    length = db.Column(db.Integer)
    aspect_ratio = db.Column(db.String(20))
    fps = db.Column(db.Float)
    main_feature = db.Column(db.Boolean)
    basename = db.Column(db.String(256))
    filename = db.Column(db.String(256))
    orig_filename = db.Column(db.String(256))
    new_filename = db.Column(db.String(256))
    ripped = db.Column(db.Boolean)
    status = db.Column(db.String(32))
    error = db.Column(db.Text)
    source = db.Column(db.String(32))

    def __init__(self, job_id, track_number, length, aspect_ratio, fps, main_feature, source, basename, filename):
        """Return a track object"""
        self.job_id = job_id
        self.track_number = track_number
        self.length = length
        self.aspect_ratio = aspect_ratio
        self.fps = fps
        self.main_feature = main_feature
        self.source = source
        self.basename = basename
        self.filename = filename
        self.ripped = False

    def __repr__(self):
        return '<Post {}>'.format(self.track_number)
    
    def write_metadata(self, destination):
        """ Write metadata to file and to the file(s) themselves"""
        pass


class Config(db.Model):
    CONFIG_ID = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.job_id'))
    ARM_CHECK_UDF = db.Column(db.Boolean)
    GET_VIDEO_TITLE = db.Column(db.Boolean)
    SKIP_TRANSCODE = db.Column(db.Boolean)
    VIDEOTYPE = db.Column(db.String(25))
    MINLENGTH = db.Column(db.String(6))
    MAXLENGTH = db.Column(db.String(6))
    MANUAL_WAIT = db.Column(db.Boolean)
    MANUAL_WAIT_TIME = db.Column(db.Integer)
    RAW_PATH = db.Column(db.String(255))
    TRANSCODE_PATH = db.Column(db.String(255))
    COMPLETED_PATH = db.Column(db.String(255))
    EXTRAS_SUB = db.Column(db.String(255))
    INSTALLPATH = db.Column(db.String(255))
    LOGPATH = db.Column(db.String(255))
    LOGLEVEL = db.Column(db.String(255))
    LOGLIFE = db.Column(db.Integer)
    DBFILE = db.Column(db.String(255))
    WEBSERVER_IP = db.Column(db.String(25))
    WEBSERVER_PORT = db.Column(db.Integer)
    SET_MEDIA_PERMISSIONS = db.Column(db.Boolean)
    CHMOD_VALUE = db.Column(db.Integer)
    SET_MEDIA_OWNER = db.Column(db.Boolean)
    CHOWN_USER = db.Column(db.String(50))
    CHOWN_GROUP = db.Column(db.String(50))
    RIPMETHOD = db.Column(db.String(25))
    MKV_ARGS = db.Column(db.String(25))
    DELRAWFILES = db.Column(db.Boolean)
    HASHEDKEYS = db.Column(db.Boolean)
    HB_PRESET_DVD = db.Column(db.String(256))
    HB_PRESET_BD = db.Column(db.String(256))
    DEST_EXT = db.Column(db.String(10))
    HANDBRAKE_CLI = db.Column(db.String(25))
    MAINFEATURE = db.Column(db.Boolean)
    HB_ARGS_DVD = db.Column(db.String(256))
    HB_ARGS_BD = db.Column(db.String(256))
    EMBY_REFRESH = db.Column(db.Boolean)
    EMBY_SERVER = db.Column(db.String(25))
    EMBY_PORT = db.Column(db.String(6))
    EMBY_CLIENT = db.Column(db.String(25))
    EMBY_DEVICE = db.Column(db.String(50))
    EMBY_DEVICEID = db.Column(db.String(128))
    EMBY_USERNAME = db.Column(db.String(50))
    EMBY_USERID = db.Column(db.String(128))
    EMBY_PASSWORD = db.Column(db.String(128))
    EMBY_API_KEY = db.Column(db.String(64))
    NOTIFY_RIP = db.Column(db.Boolean)
    NOTIFY_TRANSCODE = db.Column(db.Boolean)
    PB_KEY = db.Column(db.String(64))
    IFTTT_KEY = db.Column(db.String(64))
    IFTTT_EVENT = db.Column(db.String(25))
    PO_USER_KEY = db.Column(db.String(64))
    PO_APP_KEY = db.Column(db.String(64))
    OMDB_API_KEY = db.Column(db.String(64))

    def __init__(self, c, job_id):
        self.__dict__.update(c)
        self.job_id = job_id

    def list_params(self):
        """Returns a string of the object"""
        s = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            if s:
                s = s + "\n"
            if str(attr) in hidden_attribs and value:
                value = HIDDEN_VALUE
            s = s + str(attr) + ":" + str(value)

        return s

    def __getitem__(self, item):
        """ allows to acces the parameters with [] (for notification)"""
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError()

    def get(self, item, default=None):
        """ allows to acces the parameters with get (for notification)"""
        if hasattr(self, item):
            return getattr(self, item)
        return default
    
    def __str__(self):
        """Returns a string of the object"""
        s = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            if str(attr) in hidden_attribs and value:
                value = HIDDEN_VALUE
            s = s + "(" + str(attr) + "=" + str(value) + ") "

        return s

    def pretty_table(self):
        """Returns a string of the prettytable"""
        x = PrettyTable()
        x.field_names = ["Config", "Value"]
        x._max_width = {"Config": 20, "Value": 30}
        for attr, value in self.__dict__.items():
            if str(attr) in hidden_attribs and value:
                value = HIDDEN_VALUE
            x.add_row([str(attr), str(value)])
        return str(x.get_string())

    def get_d(self):
        r = {}
        for key, value in self.__dict__.items():
            if str(key) not in hidden_attribs:
                r[str(key)] = str(value)
        return r


class User(db.Model, UserMixin):
    user_id = db.Column(db.Integer, index=True, primary_key=True)
    email = db.Column(db.String(64))
    password = db.Column(db.String(128))
    hash = db.Column(db.String(256))

    def __init__(self, email=None, password=None, hashed=None):
        self.email = email
        self.password = password
        self.hash = hashed

    def __repr__(self):
        return '<User %r>' % (self.email)

    def get_id(self):
        return self.user_id


class AlembicVersion(db.Model):
    version_num = db.Column(db.String(36), autoincrement=False, primary_key=True)

    def __init__(self, version=None):
        self.version_num = version


class UISettings(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    use_icons = db.Column(db.Boolean)
    save_remote_images = db.Column(db.Boolean)
    bootstrap_skin = db.Column(db.String(64))
    language = db.Column(db.String(4))
    index_refresh = db.Column(db.Integer)
    database_limit = db.Column(db.Integer)

    def __init__(self, use_icons=None, save_remote_images=None, bootstrap_skin=None, language=None, index_refresh=None,
                 database_limit=None):
        self.use_icons = use_icons
        self.save_remote_images = save_remote_images
        self.bootstrap_skin = bootstrap_skin
        self.language = language
        self.index_refresh = index_refresh
        self.database_limit = database_limit

    def __repr__(self):
        return '<UISettings %r>' % self.id

    def __str__(self):
        """Returns a string of the object"""

        s = self.__class__.__name__ + ": "
        for attr, value in self.__dict__.items():
            s = s + "(" + str(attr) + "=" + str(value) + ") "

        return s

    def get_d(self):
        r = {}
        for key, value in self.__dict__.items():
            if '_sa_instance_state' not in key:
                r[str(key)] = str(value)
        return r
