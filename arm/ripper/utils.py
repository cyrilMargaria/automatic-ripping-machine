#!/usr/bin/env python3
# Collection of utility functions
# flake8: noqa: E501
import os
import sys
import yaml
import logging
import fcntl
import subprocess
import shutil
import time
import random
import re
import platform
import psutil
import apprise
from arm.config.config import cfg
from arm.ui import app, db
import arm.models.models as m
from arm.ripper.fs_utils import make_dir

NOTIFY_TITLE = "ARM notification"

# dictionary of   KEY -> lambda(cfg) -> string
# its a tad tedious, using a a schema (json schema, ..etc) to describe each url schema with helpers for configuring the notification might be nicer,
# Right now: add as you need them :-)
NOTIFICATIONS_BUILDER = {
    # boxcar://{access_key}/{secret_key}
    "BOXCAR_KEY": lambda x: f"boxcar://{x.BOXCAR_KEY}/{x.BOXCAR_SECRET}",
    # discord://{WebhookID}/{WebhookToken}/
    "DISCORD_WEBHOOK_ID": lambda x: f"discord://{x.DISCORD_WEBHOOK_ID}/{x.DISCORD_TOKEN}",
    # faast://{authorizationtoken}
    "FAAST_TOKEN": lambda x: f"faast://{x.FAAST_TOKEN}",
    # flock://{token}/
    "FLOCK_TOKEN": lambda x: f"flock://{x.FLOCK_TOKEN}",
    # gitter: // {token} / {room} /
    "GITTER_TOKEN": lambda x: f"gitter://{x.GITTER_TOKEN}/{x.GITTER_ROOM}",
    # gotify://{hostname}/{token}
    "GOTIFY_TOKEN": lambda x: f"gotify://{x.GOTIFY_HOST}/{x.GOTIFY_TOKEN}",
    # growl://{hostname} || growl://{password}@{hostname}
    "GROWL_HOST": lambda x: f"growl://{cfg_cred(x, 'GROWL_PASS', '')}{x.GROWL_HOST}",
    # join://{apikey}/ ||  join://{apikey}/{device_id}
    "JOIN_API": lambda x: f"join://{x.JOIN_API}/{x.JOIN_DEVICE}" if x.get("JOIN_DEVICE") else f"join://{x.JOIN_API}",
    # kodi://{hostname}:{port} || kodi: // {userid}: {password} @ {hostname}:{port}
    "KODI_HOST": lambda x: f"kodis://{cfg_cred(x, 'KODI_USER', 'KODI_PASS')}{x.KODI_HOST}{cfg_port(x.KODI_PORT)}" if x.get("KODI_PORT",0) == 443 else f"kodi://{cfg_cred(x, 'KODI_USER', 'KODI_PASS')}{x.KODI_HOST}{cfg_port(x.KODI_PORT)}",
    "KUMULOS_API": lambda x: f"kumulos://{x.KUMULOS_API}/{x.KUMULOS_SERVERKEY}",
    "LAMETRIC_API": lambda x: f"lametric://{x.LAMETRIC_API}@{x.LAMETRIC_HOST}",
    "LAMETRIC_APP_ID": lambda x: f"lametric://{x.LAMETRIC_APP_ID}@{x.LAMETRIC_TOKEN}",
    "MAILGUN_DOMAIN": lambda x: f"mailgun://{x.MAILGUN_USER}@{x.MAILGUN_DOMAIN}/{x.MAILGUN_APIKEY}",
    "MATRIX_HOST": lambda x: f"matrixs://{x.MATRIX_USER}:{x.MATRIX_PASS}@{x.MATRIX_HOST}",
    "MATRIX_TOKEN": lambda x: f"matrix://{x.MATRIX_TOKEN}",
    # msteams://{tokenA}/{tokenB}/{tokenC}/
    "MSTEAMS_TOKENA": lambda x: f"msteams://{x.MSTEAMS_TOKENA}/{x.MSTEAMS_TOKENB}/${x.MSTEAMS_TOKENC}/",
    "NEXTCLOUD_HOST": lambda x: f"nclouds://{x.NEXTCLOUD_ADMINUSER}:{x.NEXTCLOUD_ADMINPASS}@{x.NEXTCLOUD_HOST}/{x.NEXTCLOUD_NOTIFY_USER}",
    "NOTICA_TOKEN": lambda x: f"notica://{x.NOTICA_TOKEN}",
    "NOTIFICO_PROJECTID": lambda x: f"notica://{x.NOTIFICO_PROJECTID}/{x.NOTIFICO_MESSAGEHOOK}",
    # o365://{tenant_id}:{account_email}/{client_id}/{client_secret}/
    # TODO: we might need to escape/encode the client_secret
    "OFFICE365_TENANTID": lambda x: f"o365://{x.OFFICE365_TENANTID}:{x.OFFICE365_ACCOUNTEMAIL}/{x.OFFICE365_CLIENT_ID}/{x.OFFICE365_CLIENT_SECRET}",
    "POPCORN_EMAIL": lambda x: f"popcorn://{x.POPCORN_API}/{x.POPCORN_EMAIL}",
    "POPCORN_PHONENO": lambda x: f"popcorn://{x.POPCORN_API}/{x.POPCORN_PHONENO}",
    "PROWL_API": lambda x: f"prowl://{x.PROWL_API}/{x.PROWL_PROVIDERKEY}" if x.get("PROWL_PROVIDERKEY") else f"prowl://{x.PROWL_API}",
    "PUSHJET_HOST": lambda x: f"pjet://{x.PUSHJET_HOST}",
    "PUSH_API": lambda x: f"push://{x.PUSH_API}",
    "PUSHED_APP_KEY": lambda x: f"pushed://{x.PUSHED_APP_KEY}/{x.PUSHED_APP_SECRET}",
    "PUSHSAFER_KEY": lambda x: f"psafers://{x.PUSHSAFER_KEY}",
    # rocket://{webhook}@{hostname}/{@user}
    "ROCKETCHAT_HOST": lambda x: f"rocket://{x.ROCKETCHAT_WEBHOOK}@{x.ROCKETCHAT_HOST}",
    # ryver://{organization}/{token}/
    "RYVER_ORG": lambda x: f"ryver://{x.RYVER_ORG}/{x.RYVER_TOKEN}/",
    # sendgrid://{apikey}:{from_email}
    "SENDGRID_API": lambda x: f"sendgrid://{x.SENDGRID_API}:{x.SENDGRID_FROMMAIL}",
    # spush://{apikey}/
    "SIMPLEPUSH_API": lambda x: f"spush://{x.SIMPLEPUSH_API}",
    # slack://{tokenA}/{tokenB}/{tokenC}
    "SLACK_TOKENA": lambda x: f"slack://{x.SLACK_TOKENA}/{x.SLACK_TOKENB}/{x.SLACK_TOKENC}/{x.SLACK_CHANNEL}",
    # sparkpost://{user}@{domain}/{apikey}/ || sparkpost://{user}@{domain}/{apikey}/{email}/
    "SPARKPOST_API": lambda x: f"sparkpost://{x.SPARKPOST_USER}@{x.SPARKPOST_HOST}/{x.SPARKPOST_API}/{x.SPARKPOST_EMAIL}",
    # spontit://{user}@{apikey}
    "SPONTIT_API": lambda x: f"spontit://{x.SPONTIT_USER_ID}@{x.SPONTIT_API}",
    # tgram://{bot_token}/{chat_id}/ || tgram://{bot_token}/
    "TELEGRAM_BOT_TOKEN": lambda x: f"tgram://{x.TELEGRAM_BOT_TOKEN}/{x.TELEGRAM_CHAT_ID}",
    # twist://{email}/{password} || twist://{password}:{email}
    "TWIST_EMAIL": lambda x: f"twist://{x.TWIST_EMAIL}/{x.TWIST_PASS}",
    # xbmc://{userid}:{password}@{hostname}:{port} ||  xbmc://{hostname}:{port}
    "XBMC_HOST": lambda x: f"xbmc://{cfg_cred(x, 'XBMC_USER', 'XBMC_PASS')}{x.XBMC_HOST}{cfg_port(x.XBMC_PORT)}",
    # xmpp://{password}@{hostname}:{port} || xmpps://{userid}:{password}@{hostname}
    "XMPP_HOST": lambda x: f"xmpps://{cfg_cred(x, 'XMPP_USER','XMPP_PASS')}{x.XMPP_HOST}" if x.get("XMPP_USER") else f"xmpp://{x.XMPP_PASS}@{x.XMPP_HOST}",
    # wxteams://{token}/
    "WEBEX_TEAMS_TOKEN": lambda x: f"wxteams://{x.WEBEX_TEAMS_TOKEN}",
    # zulip://{botname}@{organization}/{token}/
    "ZILUP_CHAT_TOKEN": lambda x: f"zulip://{x.ZILUP_CHAT_BOTNAME}@{x.ZILUP_CHAT_ORG}/{x.ZILUP_CHAT_TOKEN}"
}

def cfg_port(port):
    if port:
        return f":{port}"
    return ""

def cfg_cred(configuration, user_key, pass_key):
    """ return apprise credentials if set , else empty string"""
    user = configuration.get(user_key)
    passwd = ""
    if pass_key:
        passwd = configuration.get(pass_key)
    if user and passwd:
        return f"{user}:{passwd}@"
    elif passwd:
        return f"{passwd}@"
    elif user:
        return f"{user}@"
    return ""

# same for job.config
NOTIFICATION_CONFIG_BUILDER = {
    # Pushbullet
    # pbul://{accesstoken}
    "PB_KEY": lambda x: f"pbul://{x.PB_KEY}",
    # ifttt://{WebhookID}@{Event}/
    "IFTTT_KEY": lambda x: f"ifttt://{x.IFTTT_KEY}@{x.IFTTT_EVENT}",
    "PO_USER_KEY": lambda x: f"pover://{x.PO_USER_KEY}@{x.PO_APP_KEY}",
    "JSON_URL": lambda x : str(x["JSON_URL"]).replace("http://", "json://").replace("https://", "jsons://"),
}

def notification_urls_from_cfg(configuration, urls_config):
    """
       Build list of URLs to use based on:
        - configuration : object holding the configuration, must support get() and [] (models.config and config.cfg do)
        - urls_config: dict of config key -> callable that is called with the configuration
    """
    # call the callable for all defined keys in configuration
    return [v(configuration) for k, v in urls_config.items() if configuration.get(k)]


def notify(job, title, body):
    """Send notifications
     title = title for notification
    body = body of the notification
    """

   

    # Prepend Site Name if configured, append Job ID if configured
    if cfg["ARM_NAME"] != "":
        title = f"[{cfg['ARM_NAME']}] - {title}"
    if cfg["NOTIFY_JOBID"]:
        title = f"{title} - {job.job_id}"

    # Create an Apprise instance
    apobj = apprise.Apprise()
    for u in notification_urls_from_cfg(job.config, NOTIFICATION_CONFIG_BUILDER):
        apobj.add(u)
    try:
        apobj.notify(body, title=title)
    except Exception as e:  # noqa: E722
        logging.error(f"Failed sending notifications. error:{e}. Continuing processing...")

    if cfg["APPRISE"] != "":
        try:
            apprise_notify(cfg["APPRISE"], title, body)
            logging.debug("apprise-config: " + str(cfg["APPRISE"]))
        except Exception as e:  # noqa: E722
            logging.error("Failed sending apprise notifications. " + str(e))


def notify_entry(job):
    # Notify On Entry
    if job.disctype in ["dvd", "bluray"]:
        # Send the notifications
        notify(job, NOTIFY_TITLE,
               f"Found disc: {job.title}. Disc type is {job.disctype}. Main Feature is {cfg['MAINFEATURE']}"
               f".  Edit entry here: http://{check_ip()}:"
               f"{cfg['WEBSERVER_PORT']}/jobdetail?job_id={job.job_id}")
    elif job.disctype == "music":
        notify(job, NOTIFY_TITLE, f"Found music CD: {job.label}. Ripping all tracks")
    elif job.disctype == "data":
        notify(job, NOTIFY_TITLE, "Found data disc.  Copying data.")
    else:
        notify(job, NOTIFY_TITLE, "Could not identify disc.  Exiting.")
        sys.exit()


def scan_emby(job):
    """Trigger a media scan on Emby"""

    if cfg["EMBY_REFRESH"]:
        logging.info("Sending Emby library scan request")
        url = f"http://{cfg['EMBY_SERVER']}:{cfg['EMBY_PORT']}/Library/Refresh?api_key={cfg['EMBY_API_KEY']}"
        try:
            req = requests.post(url)
            if req.status_code > 299:
                req.raise_for_status()
            logging.info("Emby Library Scan request successful")
        except requests.exceptions.HTTPError:
            logging.error(f"Emby Library Scan request failed with status code: {req.status_code}")
    else:
        logging.info("EMBY_REFRESH config parameter is false.  Skipping emby scan.")


def sleep_check_process(process_str, transcode_limit):
    """ New function to check for max_transcode from cfg file and force obey limits\n
    arguments:
    process_str - The process string from arm.yaml
    transcode_limit - The user defined limit for maximum transcodes\n\n

    returns:
    True - when we have space in the transcode queue
    """
    if transcode_limit > 0:
        loop_count = transcode_limit + 1
        logging.debug("loop_count " + str(loop_count))
        logging.info("Starting A sleep check of " + str(process_str))
        while loop_count >= transcode_limit:
            loop_count = sum(1 for proc in psutil.process_iter() if proc.name() == process_str)
            logging.debug(f"Number of Processes running is: {loop_count} going to waiting 12 seconds.")
            if transcode_limit > loop_count:
                return True
            # Try to make each check at different times
            x = random.randrange(20, 120, 10)
            logging.debug(f"sleeping for {x} seconds")
            time.sleep(x)
    else:
        logging.info("Transcode limit is disabled")


def convert_job_type(video_type):
    if video_type == "movie":
        type_sub_folder = "movies"
    elif video_type == "series":
        type_sub_folder = "tv"
    else:
        type_sub_folder = "unidentified"
    return type_sub_folder


def fix_job_title(job):
    if job.year and job.year != "0000" and job.year != "":
        job_title = f"{job.title} ({job.year})"
    else:
        job_title = f"{job.title}"
    return job_title


def move_files(basepath, filename, job, ismainfeature=False):
    """Move files into final media directory\n
    basepath = path to source directory\n
    filename = name of file to be moved\n
    job = instance of Job class\n
    ismainfeature = True/False"""
    type_sub_folder = convert_job_type(job.video_type)
    videotitle = fix_job_title(job)

    logging.debug(f"Arguments: {basepath} : {filename} : {job.hasnicetitle} : {videotitle} : {ismainfeature}")
    m_path = os.path.join(cfg["COMPLETED_PATH"], str(type_sub_folder), videotitle)
    # For series there are no extras as we never get a main feature
    e_path = os.path.join(m_path, cfg["EXTRAS_SUB"]) if job.video_type != "series" else m_path
    make_dir(m_path)

    if ismainfeature is True:
        logging.info(f"Track is the Main Title.  Moving '{filename}' to {m_path}")
        m_file = os.path.join(m_path, videotitle + "." + cfg["DEST_EXT"])
        if not os.path.isfile(m_file):
            try:
                shutil.move(os.path.join(basepath, filename), m_file)
            except Exception as e:
                logging.error(f"Unable to move '{filename}' to '{m_path}' - Error: {e}")
        else:
            logging.info(f"File: {m_file} already exists.  Not moving.")
    else:
        make_dir(e_path)
        logging.info(f"Moving '{filename}' to {e_path}")
        e_file = os.path.join(e_path, videotitle + "." + cfg["DEST_EXT"])
        if not os.path.isfile(e_file):
            try:
                shutil.move(os.path.join(basepath, filename), os.path.join(e_path, filename))
            except Exception as e:
                logging.error(f"Unable to move '{filename}' to {e_path} - {e}")
        else:
            logging.info(f"File: {e_file} already exists.  Not moving.")


def get_cdrom_status(devpath):
    """get the status of the cdrom drive\n
    devpath = path to cdrom\n

    returns int
    CDS_NO_INFO		0\n
    CDS_NO_DISC		1\n
    CDS_TRAY_OPEN		2\n
    CDS_DRIVE_NOT_READY	3\n
    CDS_DISC_OK		4\n

    see linux/cdrom.h for specifics\n
    """

    
    if platform.system() != 'Linux':
        return 4
    try:
        fd = os.open(devpath, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        # Sometimes ARM will log errors opening hard drives. this check should stop it
        if not re.search(r'hd[a-j]|sd[a-j]|loop[0-9]', devpath):
            logging.info(f"Failed to open device {devpath} to check status.")
        exit(2)
    result = fcntl.ioctl(fd, 0x5326, 0)

    return result


def find_file(filename, search_path):
    """
    Check to see if file exists by searching a directory recursively\n
    filename = filename to look for\n
    search_path = path to search recursively\n

    returns True or False
    """

    for dirpath, dirnames, filenames in os.walk(search_path):
        if filename in filenames:
            return True
    return False


def rip_music(job, logfile):
    """
    Rip music CD using abcde using abcde config\n
    job = job object\n
    logfile = location of logfile\n

    returns True/False for success/fail
    """

    abcfile = cfg["ABCDE_CONFIG_FILE"]
    if job.disctype == "music":
        logging.info("Disc identified as music")
        # If user has set a cfg file with ARM use it
        if os.path.isfile(abcfile):
            cmd = f'abcde -d "{job.devpath}" -c {abcfile} >> "{logfile}" 2>&1'
        else:
            cmd = f'abcde -d "{job.devpath}" >> "{logfile}" 2>&1'

        logging.debug(f"Sending command: {cmd}")

        try:
            subprocess.check_output(cmd, shell=True).decode("utf-8")
            logging.info("abcde call successful")
            return True
        except subprocess.CalledProcessError as ab_error:
            err = f"Call to abcde failed with code: {ab_error.returncode} ({ab_error.output})"
            logging.error(err)
    return False


def rip_data(job, datapath, logfile):
    """
    Rip data disc using dd on the command line\n
    job = job object\n
    datapath = path to copy data to\n
    logfile = location of logfile\n

    returns True/False for success/fail
    """

    if job.disctype == "data":
        logging.info("Disc identified as data")

        if job.label == "" or job.label is None:
            job.label = "datadisc"

        incomplete_filename = os.path.join(datapath, job.label + ".part")
        final_filename = os.path.join(datapath, job.label + ".iso")

        logging.info("Ripping data disc to: " + incomplete_filename)

        # Added from pull 366
        cmd = 'dd if="{0}" of="{1}" {2} 2>> {3}'.format(
            job.devpath,
            incomplete_filename,
            cfg["DATA_RIP_PARAMETERS"],
            logfile
        )

        logging.debug("Sending command: " + cmd)

        try:
            subprocess.check_output(
                cmd,
                shell=True
            ).decode("utf-8")
            logging.info("Data rip call successful")
            os.rename(incomplete_filename, final_filename)
            return True
        except subprocess.CalledProcessError as dd_error:
            err = "Data rip failed with code: " + str(dd_error.returncode) + "(" + str(dd_error.output) + ")"
            logging.error(err)
            os.unlink(incomplete_filename)
            # sys.exit(err)

    return False


def set_permissions(job, directory_to_traverse):
    if not cfg['SET_MEDIA_PERMISSIONS']:
        return False
    try:
        corrected_chmod_value = int(str(cfg["CHMOD_VALUE"]), 8)
        logging.info("Setting permissions to: " + str(cfg["CHMOD_VALUE"]) + " on: " + directory_to_traverse)
        os.chmod(directory_to_traverse, corrected_chmod_value)
        if job.config.SET_MEDIA_OWNER and job.config.CHOWN_USER and job.config.CHOWN_GROUP:
            import pwd
            import grp
            uid = pwd.getpwnam(job.config.CHOWN_USER).pw_uid
            gid = grp.getgrnam(job.config.CHOWN_GROUP).gr_gid
            os.chown(directory_to_traverse, uid, gid)

        for dirpath, l_directories, l_files in os.walk(directory_to_traverse):
            for cur_dir in l_directories:
                logging.debug("Setting path: " + cur_dir + " to permissions value: " + str(cfg["CHMOD_VALUE"]))
                os.chmod(os.path.join(dirpath, cur_dir), corrected_chmod_value)
                if job.config.SET_MEDIA_OWNER:
                    os.chown(os.path.join(dirpath, cur_dir), uid, gid)
            for cur_file in l_files:
                logging.debug("Setting file: " + cur_file + " to permissions value: " + str(cfg["CHMOD_VALUE"]))
                os.chmod(os.path.join(dirpath, cur_file), corrected_chmod_value)
                if job.config.SET_MEDIA_OWNER:
                    os.chown(os.path.join(dirpath, cur_file), uid, gid)
        logging.info("Permissions set successfully: True")
    except Exception as e:
        logging.error(f"Permissions setting failed as: {e}")




def put_track(job, t_no, seconds, aspect, fps, mainfeature, source, filename=""):
    """
    Put data into a track instance\n


    job = job ID\n
    t_no = track number\n
    seconds = lenght of track in seconds\n
    aspect = aspect ratio (ie '16:9')\n
    fps = frames per second (float)\n
    mainfeature = True/False\n
    source = Source of information\n
    filename = filename of track\n
    """

    logging.debug(
        f"Track #{t_no} Length: {seconds} fps: {fps} aspect: {aspect} Mainfeature: {mainfeature} Source:  {source}")

    t = m.Track(
        job_id=job.job_id,
        track_number=t_no,
        length=seconds,
        aspect_ratio=aspect,
        fps=fps,
        main_feature=mainfeature,
        source=source,
        basename=job.title,
        filename=filename
    )
    t.ripped = True if seconds > int(cfg['MINLENGTH']) else False
    db.session.add(t)
    db.session.commit()


def arm_setup():
    """
    setup arm - make sure everything is fully setup and ready and there are no errors. This is still in dev. ATM

    :arguments
    None

    :return
    None
    """
    try:
        # Make the Raw dir if it doesnt exist
        if not os.path.exists(cfg['RAW_PATH']):
            os.makedirs(cfg['RAW_PATH'])
        # Make the Transcode dir if it doesnt exist
        if not os.path.exists(cfg['TRANSCODE_PATH']):
            os.makedirs(cfg['TRANSCODE_PATH'])
        # Make the Complete dir if it doesnt exist
        if not os.path.exists(cfg['COMPLETED_PATH']):
            os.makedirs(cfg['COMPLETED_PATH'])
        # Make the log dir if it doesnt exist
        if not os.path.exists(cfg['LOGPATH']):
            os.makedirs(cfg['LOGPATH'])
    except IOError as e:  # noqa: F841
        logging.error(f"A fatal error has occurred.  Cant find/create the folders from arm.yaml - Error:{e}")


def database_updater(args, job, wait_time=90):
    """
    Try to update our db for x seconds and handle it nicely if we cant

    :param args: This needs to be a Dict with the key being the job.method you want to change and the value being
    the new value. If args isn't a dict assume we are wanting a rollback

    :param job: This is the job object
    :param wait_time: The time to wait in seconds
    :return: Nothing
    """
    if type(args) is not dict:
        db.session.rollback()
        return False
    else:
        # Loop through our args and try to set any of our job variables
        for (key, value) in args.items():
            setattr(job, key, value)
            logging.debug(f"{key}={value}")
    for i in range(wait_time):  # give up after the users wait period in seconds
        try:
            db.session.commit()
        except Exception as e:
            if "locked" in str(e):
                time.sleep(1)
                logging.debug(f"database is locked - try {i}/{wait_time}")
            else:
                logging.debug(f"Error: {e}")
                raise RuntimeError(str(e))
        else:
            logging.debug("successfully written to the database")
            return True


def database_adder(obj_class):
    for i in range(90):  # give up after the users wait period in seconds
        try:
            logging.debug(f"Trying to add {type(obj_class).__name__}")
            db.session.add(obj_class)
            db.session.commit()
        except Exception as e:
            if "locked" in str(e):
                time.sleep(1)
                logging.debug(f"database is locked - try {i}/90")
            else:
                logging.error(f"Error: {e}")
                raise RuntimeError(str(e))
        else:
            logging.debug(f"successfully written {type(obj_class).__name__} to the database")
            return True


def clean_old_jobs():
    a_jobs = db.session.query(m.Job).filter(m.Job.status.notin_(['fail', 'success'])).all()
    # Clean up abandoned jobs
    for j in a_jobs:
        if psutil.pid_exists(j.pid):
            p = psutil.Process(j.pid)
            if j.pid_hash == hash(p):
                logging.info(f"Job #{j.job_id} with PID {j.pid} is currently running.")
        else:
            logging.info(f"Job #{j.job_id} with PID {j.pid} has been abandoned."
                         f"Updating job status to fail.")
            j.status = "fail"
            db.session.commit()


def job_dupe_check(job):
    """
    function for checking the database to look for jobs that have completed
    successfully with the same crc

    :param job: The job obj so we can use the crc/title etc
    :return: True if we have found dupes with the same crc
              - Will also return a dict of all the jobs found.
             False if we didnt find any with the same crc
              - Will also return None as a secondary param
    """
    if job.crc_id is None:
        return False, None
    logging.debug(f"trying to find jobs with crc64={job.crc_id}")
    previous_rips = m.Job.query.filter_by(crc_id=job.crc_id, status="success", hasnicetitle=True)
    r = {}
    i = 0
    for j in previous_rips:
        logging.debug("job obj= " + str(j.get_d()))
        x = j.get_d().items()
        r[i] = {}
        for key, value in iter(x):
            r[i][str(key)] = str(value)
        i += 1

    logging.debug(f"previous rips = {r}")
    if r:
        logging.debug(f"we have {len(r)} jobs")
        # This might need some tweaks to because of title/year manual
        title = r[0]['title'] if r[0]['title'] else job.label
        year = r[0]['year'] if r[0]['year'] != "" else ""
        poster_url = r[0]['poster_url'] if r[0]['poster_url'] != "" else None
        hasnicetitle = bool(r[0]['hasnicetitle']) if r[0]['hasnicetitle'] else False
        video_type = r[0]['video_type'] if r[0]['hasnicetitle'] != "" else "unknown"
        active_rip = {
            "title": title, "year": year, "poster_url": poster_url, "hasnicetitle": hasnicetitle,
            "video_type": video_type}
        database_updater(active_rip, job)
        return True, r

    logging.debug("we have no previous rips/jobs matching this crc64")
    return False, None


def check_ip():
    """
        Check if user has set an ip in the config file
        if not gets the most likely ip
        arguments:
        none
        return: the ip of the host or 127.0.0.1
    """
    host = cfg['WEBSERVER_IP']
    if host == 'x.x.x.x':
        # autodetect host IP address
        from netifaces import interfaces, ifaddresses, AF_INET
        ip_list = []
        for interface in interfaces():
            inet_links = ifaddresses(interface).get(AF_INET, [])
            for link in inet_links:
                ip = link['addr']
                # print(str(ip))
                if ip != '127.0.0.1' and not (ip.startswith('172')):
                    ip_list.append(ip)
                    # print(str(ip))
        if len(ip_list) > 0:
            return ip_list[0]
        else:
            return '127.0.0.1'
    else:
        return host


def apprise_notify(apprise_cfg, title, body):
    """APPRISE NOTIFICATIONS

    :argument
    apprise_cfg - The full path to the apprise.yaml file
    title - the message title
    body - the main body of the message

    :returns
    nothing
    """

    cfg = {}
    yamlfile = apprise_cfg
    with open(yamlfile, "r") as f:
        cfg = yaml.safe_load(f)
    cfg = dictProxy(cfg)
    
    urls = ["dbus://", "kde://", "gnome://", "windows://"]
    if platform.system() == 'Linux':
        urls.extend(["dbus://", "kde://", "gnome://"])
    elif platform.system() == 'Darwin':
        urls.extend(["macosx://"])
    elif platform.system() == 'Windows':
        urls.extend(["windows://"])
    
    urls.extend(notification_urls_from_cfg(cfg, NOTIFICATIONS_BUILDER))
    # Create an Apprise instance
    apobj = apprise.Apprise()
    for url in urls:
        apobj.add(url)
        
    try:
        apobj.notify(
            body,
            title=title,
        )
    except:  # noqa: E722
        logging.error("Failed sending Pushbullet apprise notification.  Continuing processing...")

class dictProxy:
    """
      Allow attribute access to a dictionary
      This allows nice format strings
    """
    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        if hasattr(self._data, name):
            return getattr(self._data, name)
        return self._data.get(name)

    def __getitem__(self, item):
        return self._data[item]    
