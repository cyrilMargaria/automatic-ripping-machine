#!/usr/bin/env python3

import sys
import argparse  # noqa: E402
import os  # noqa: E402
import os.path
import logging  # noqa: E402
import time  # noqa: E402
import datetime  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import getpass  # noqa E402
import psutil  # noqa E402
import platform
import arm
from  arm.ripper import logger, utils, makemkv, handbrake, identify, fs_utils  # noqa: E402
import arm.db as dbutil
from  arm.db import db
from arm.config.config import cfg  # noqa: E402

from arm.ripper.getkeys import grabkeys  # noqa: E402
from arm.models.models import Job, Config  # noqa: E402
import arm.ui
NOTIFY_TITLE = "ARM notification"
PROCESS_COMPLETE = " processing complete. "


def parse_args():
    """ Parse_Args to program, parses arguments"""
    parser = argparse.ArgumentParser(description='Process disc using ARM')
    parser.add_argument('-d', '--devpath', help='Device path ', required=True)
    parser.add_argument('-w', '--wait', dest='wait', action="store_true", help='Wait for device to be present')
    parser.add_argument('-L', dest='log_level', help="log level", default="INFO")
    parser.add_argument('-c', dest='config_file', help="""
       configuration file, can be also set in environment var ARM_CONFIG_FILE.
       The value can be a file or an url and contain
       the following variables:
        - hostname : node hostname (here {hostname})
        - devpath
      for instance: http://cfgs.example.net/configs/{{hostname}}.yml
      """.format(hostname=platform.node()))
    return parser.parse_args()


def log_udev_params(devpath):
    """log all udev parameters"""

    logging.debug("**** Logging udev attributes ****")
    try:
        import pyudev  # noqa: E402
        # logging.info("**** Start udev attributes ****")
        context = pyudev.Context()
        device = pyudev.Devices.from_device_file(context, '/dev/sr0')
        for key, value in device.items():
            logging.debug(key + ":" + value)
    except Exception:
        logging.debug("****  pyudev not available ****")

    logging.debug("**** End udev attributes ****")


def log_arm_params(job):
    """log all entry parameters"""

    # log arm parameters
    logging.info("**** Logging ARM variables ****")
    for key in ("devpath", "mountpoint", "title", "year", "video_type",
                "hasnicetitle", "label", "disctype"):
        logging.info(
            key + ": " + str(getattr(job, key)))
    logging.info("**** End of ARM variables ****")

    logging.info("**** Logging config parameters ****")
    for key in ("SKIP_TRANSCODE", "MAINFEATURE", "MINLENGTH", "MAXLENGTH",
                "VIDEOTYPE", "MANUAL_WAIT", "MANUAL_WAIT_TIME", "RIPMETHOD",
                "MKV_ARGS", "DELRAWFILES", "HB_PRESET_DVD", "HB_PRESET_BD",
                "HB_ARGS_DVD", "HB_ARGS_BD", "RAW_PATH", "TRANSCODE_PATH",
                "COMPLETED_PATH", "EXTRAS_SUB", "EMBY_REFRESH", "EMBY_SERVER",
                "EMBY_PORT", "NOTIFY_RIP", "NOTIFY_TRANSCODE",
                "MAX_CONCURRENT_TRANSCODES"):
        logging.info(key.lower() +
                     ": " +
                     str(cfg.get(key, '<not given>')))
    logging.info("**** End of config parameters ****")



def skip_transcode(job, hb_out_path, hb_in_path, mkv_out_path, type_sub_folder):
    """
    For when skipping transcode in enabled
    """
    logging.info("SKIP_TRANSCODE is true.  Moving raw mkv files.")
    logging.info("NOTE: Identified main feature may not be actual main feature")
    files = os.listdir(mkv_out_path)
    final_directory = hb_out_path
    if job.video_type == "movie":
        logging.debug(f"Videotype: {job.video_type}")
        # if videotype is movie, then move biggest title to media_dir
        # move the rest of the files to the extras folder

        # find largest filesize
        logging.debug("Finding largest file")
        largest_file_name = ""
        for f in files:
            # initialize largest_file_name
            if largest_file_name == "":
                largest_file_name = f
            temp_path_f = os.path.join(hb_in_path, f)
            temp_path_largest = os.path.join(hb_in_path, largest_file_name)
            if os.stat(temp_path_f).st_size > os.stat(temp_path_largest).st_size:
                largest_file_name = f
        # largest_file should be largest file
        logging.debug(f"Largest file is: {largest_file_name}")
        temp_path = os.path.join(hb_in_path, largest_file_name)
        if os.stat(temp_path).st_size > 0:  # sanity check for filesize
            for file in files:
                # move main into media_dir
                # move others into extras folder
                if file == largest_file_name:
                    # largest movie
                    utils.move_files(hb_in_path, file, job, True)
                else:
                    # other extras
                    if not str(cfg["EXTRAS_SUB"]).lower() == "none":
                        utils.move_files(hb_in_path, file, job, False)
                    else:
                        logging.info(f"Not moving extra: {file}")
        # Change final path (used to set permissions)
        final_directory = os.path.join(cfg["COMPLETED_PATH"], str(type_sub_folder),
                                       f"{job.title} ({job.year})")
        # Clean up
        logging.debug(f"Attempting to remove extra folder in TRANSCODE_PATH: {hb_out_path}")
        if hb_out_path != final_directory:
            try:
                shutil.rmtree(hb_out_path)
                logging.debug(f"Removed sucessfully: {hb_out_path}")
            except Exception:
                logging.debug(f"Failed to remove: {hb_out_path}")
    else:
        # if videotype is not movie, then move everything
        # into 'Unidentified' folder
        logging.debug("Videotype: " + job.video_type)

        for f in files:
            mkvoutfile = os.path.join(mkv_out_path, f)
            logging.debug(f"Moving file: {mkvoutfile} to: {hb_out_path} {f}")
            utils.move_files(mkv_out_path, f, job, False)
    # remove raw files, if specified in config
    if cfg["DELRAWFILES"]:
        logging.info("Removing raw files")
        shutil.rmtree(mkv_out_path)

    utils.set_permissions(job, final_directory)
    utils.notify(job, NOTIFY_TITLE, str(job.title) + PROCESS_COMPLETE)
    logging.info("ARM processing complete")
    # WARN  : might cause issues
    # We need to update our job before we quit
    # It should be safe to do this as we aren't waiting for transcode
    job.status = "success"
    job.path = hb_out_path
    dbutil.commit()
    job.eject()
    sys.exit()


def main(logfile, job):
    """main disc processing function"""
    logging.info("Starting Disc identification")

    identify.identify(job, logfile)
    # Check db for entries matching the crc and successful
    have_dupes, crc_jobs = utils.job_dupe_check(job)
    logging.debug(f"Value of have_dupes: {have_dupes}")

    utils.notify_entry(job)

    #  If we have have waiting for user input enabled
    wait_user_input = cfg["MANUAL_WAIT"]
    if job.disctype == "data" and cfg.get("MANUAL_WAIT_DATA"):
        wait_user_input = cfg.get("MANUAL_WAIT_DATA")
    if wait_user_input:
        logging.info(f"Waiting {wait_user_input} seconds for manual override.")
        job.status = "waiting"
        dbutil.commit()
        sleep_time = 0
        while sleep_time < wait_user_input:
            time.sleep(5)
            sleep_time += 5
            db.session.refresh(job)
            db.session.refresh(job.config)
            if job.title_manual:
                break
        job.status = "active"
        dbutil.commit()

    # If the user has set info manually update database and hasnicetitle
    if job.title_manual:
        logging.info("Manual override found.  Overriding auto identification values.")
        job.updated = True
        # We need to let arm know we have a nice title so it can use the MEDIA folder and not the ARM folder
        job.hasnicetitle = True
    else:
        logging.info("No manual override found.")

    log_arm_params(job)
    fs_utils.check_fstab(job)
    grabkeys(cfg["HASHEDKEYS"])

    # Entry point for dvd/bluray
    if job.disctype in ["dvd", "bluray"]:
        # get filesystem in order
        # If we have a nice title/confirmed name use the MEDIA_DIR and not the ARM unidentified folder
        # if job.hasnicetitle:
        type_sub_folder = utils.convert_job_type(job.video_type)

        if job.year and job.year != "0000" and job.year != "":
            hb_out_path = os.path.join(cfg["TRANSCODE_PATH"], str(type_sub_folder),
                                       str(job.title) + " (" + str(job.year) + ")")
        else:
            hb_out_path = os.path.join(cfg["TRANSCODE_PATH"], str(type_sub_folder), str(job.title))

        # The dvd directory already exists - Lets make a new one using random numbers
        if (fs_utils.make_dir(hb_out_path)) is False:
            logging.info(f"Handbrake Output directory \"{hb_out_path}\" already exists.")
            # Only begin ripping if we are allowed to make duplicates
            # Or the successful rip of the disc is not found in our database
            logging.debug(f"Value of ALLOW_DUPLICATES: {0}".format(cfg["ALLOW_DUPLICATES"]))
            logging.debug(f"Value of have_dupes: {have_dupes}")
            if cfg["ALLOW_DUPLICATES"] or not have_dupes:
                ts = round(time.time() * 100)
                hb_out_path = hb_out_path + "_" + str(ts)

                if (fs_utils.make_dir(hb_out_path)) is False:
                    # We failed to make a random directory, most likely a permission issue
                    logging.exception(
                        "A fatal error has occurred and ARM is exiting.  "
                        "Couldn't create filesystem. Possible permission error")
                    utils.notify(job, NOTIFY_TITLE, "ARM encountered a fatal error processing " + str(
                        job.title) + ".  Couldn't create filesystem. Possible permission error. ")
                    job.status = "fail"
                    dbutil.commit()
                    sys.exit()
            else:
                # We arent allowed to rip dupes, notify and exit
                logging.info("Duplicate rips are disabled.")
                utils.notify(job, NOTIFY_TITLE, "ARM Detected a duplicate disc. For " + str(
                    job.title) + ".  Duplicate rips are disabled. You can re-enable them from your config file. ")
                job.eject()
                job.status = "fail"
                dbutil.commit()
                sys.exit()

        # Use FFMPeg to convert Large Poster if enabled in config
        if job.disctype == "dvd" and cfg["RIP_POSTER"]:
            _, _, _, mounted = fs_utils.get_device_mount_point(job.devpath)
            if not mounted:
                fs_utils.mount_device(job.devpath)
            if os.path.isfile(job.mountpoint+"/JACKET_P/J00___5L.MP2"):
                logging.info("Converting NTSC Poster Image")
                os.system('ffmpeg -i "'+job.mountpoint+'/JACKET_P/J00___5L.MP2" "'+hb_out_path+'/poster.png"')
            elif os.path.isfile(job.mountpoint+"/JACKET_P/J00___6L.MP2"):
                logging.info("Converting PAL Poster Image")
                os.system('ffmpeg -i "'+job.mountpoint+'/JACKET_P/J00___6L.MP2" "'+hb_out_path+'/poster.png"')
            # FS wants it mounted, keep it mounted
            if not mounted:
                fs_utils.unmount_device(job.devpath)

        logging.info(f"Processing files to: {hb_out_path}")
        mkvoutpath = None
        # entry point for bluray
        # or
        # dvd with MAINFEATURE off and RIPMETHOD mkv
        hb_in_path = str(job.devpath)
        if job.disctype == "bluray" or (not cfg["MAINFEATURE"] and cfg["RIPMETHOD"] == "mkv"):
            # send to makemkv for ripping
            # run MakeMKV and get path to output
            job.status = "ripping"
            dbutil.commit()
            try:
                mkvoutpath = makemkv.makemkv(logfile, job)
            except:  # noqa: E722
                raise

            if mkvoutpath is None:
                logging.error("MakeMKV did not complete successfully.  Exiting ARM!")
                job.status = "fail"
                dbutil.commit()
                sys.exit()
            if cfg["NOTIFY_RIP"]:
                utils.notify(job, NOTIFY_TITLE, f"{job.title} rip complete. Starting transcode. ")
            # point HB to the path MakeMKV ripped to
            hb_in_path = mkvoutpath

            # Entry point for not transcoding
            if cfg["SKIP_TRANSCODE"] and cfg["RIPMETHOD"] == "mkv":
                skip_transcode(job, hb_out_path, hb_in_path, mkvoutpath, type_sub_folder)
        job.path = hb_out_path
        job.status = "transcoding"
        dbutil.commit()
        if job.disctype == "bluray" and cfg["RIPMETHOD"] == "mkv":
            handbrake.handbrake_mkv(hb_in_path, hb_out_path, logfile, job)
            job.eject()
        elif job.disctype == "dvd" and (not cfg["MAINFEATURE"] and cfg["RIPMETHOD"] == "mkv"):
            handbrake.handbrake_mkv(hb_in_path, hb_out_path, logfile, job)
            job.eject()
        elif job.video_type == "movie" and cfg["MAINFEATURE"] and job.hasnicetitle:
            handbrake.handbrake_mainfeature(hb_in_path, hb_out_path, logfile, job)
            job.eject()
        else:
            handbrake.handbrake_all(hb_in_path, hb_out_path, logfile, job)
            job.eject()

        # check if there is a new title and change all filenames
        # time.sleep(60)
        db.session.refresh(job)
        logging.debug(f"New Title is {job.title}")
        if job.year and job.year != "0000" and job.year != "":
            final_directory = os.path.join(job.config.COMPLETED_PATH, str(type_sub_folder),
                                           f'{job.title} ({job.year})')
        else:
            final_directory = os.path.join(job.config.COMPLETED_PATH, str(type_sub_folder), str(job.title))

        # move to media directory
        tracks = job.tracks.filter_by(ripped=True)

        if job.video_type == "movie":
            for track in tracks:
                logging.info(f"Moving Movie {track.filename} to {final_directory}")
                if tracks.count() == 1:
                    utils.move_files(hb_out_path, track.filename, job, True)
                else:
                    utils.move_files(hb_out_path, track.filename, job, track.main_feature)
        # move to media directory
        elif job.video_type == "series":
            for track in tracks:
                logging.info(f"Moving Series {track.filename} to {final_directory}")
                utils.move_files(hb_out_path, track.filename, job, False)
        else:
            for track in tracks:
                logging.info(f"Type is 'unknown' or we dont have a nice title - "
                             f"Moving {track.filename} to {final_directory}")
                if tracks.count() == 1:
                    utils.move_files(hb_out_path, track.filename, job, True)
                else:
                    utils.move_files(hb_out_path, track.filename, job, track.main_feature)
                track.write_metadata(final_directory)
        # move movie poster
        src_poster = os.path.join(hb_out_path, "poster.png")
        dst_poster = os.path.join(final_directory, "poster.png")
        if os.path.isfile(src_poster):
            if not os.path.isfile(dst_poster):
                try:
                    shutil.move(src_poster, dst_poster)
                except Exception as e:
                    logging.error(f"Unable to move poster.png to '{final_directory}' - Error: {e}")
            else:
                logging.info("File: poster.png already exists.  Not moving.")

        utils.scan_emby(job)
        utils.set_permissions(job, final_directory)
        job.write_metadata(final_directory)
        # Clean up bluray backup
        if cfg["DELRAWFILES"]:
            raw_list = [mkvoutpath, hb_out_path, hb_in_path]
            for raw_folder in raw_list:
                if not raw_folder:
                    continue
                # if in path is the devpath
                if raw_folder == job.devpath:
                    continue
                try:
                    logging.info(f"Removing raw path - {raw_folder}")
                    if raw_folder != final_directory:
                        shutil.rmtree(raw_folder)
                except UnboundLocalError as e:
                    logging.debug(f"No raw files found to delete in {raw_folder}- {e}")
                except OSError as e:
                    logging.debug(f"No raw files found to delete in {raw_folder} - {e}")
                except TypeError as e:
                    logging.debug(f"No raw files found to delete in {raw_folder} - {e}")
        # report errors if any
        if cfg["NOTIFY_TRANSCODE"]:
            if job.errors:
                errlist = ', '.join(job.errors)
                utils.notify(job, NOTIFY_TITLE,
                             f" {job.title} processing completed with errors. "
                             f"Title(s) {errlist} failed to complete. ")
                logging.info(f"Transcoding completed with errors.  Title(s) {errlist} failed to complete. ")
            else:
                utils.notify(job, NOTIFY_TITLE, str(job.title) + PROCESS_COMPLETE)
        job.eject()
        logging.info("ARM processing complete")

    elif job.disctype == "music":
        if utils.rip_music(job, logfile):
            utils.notify(job, NOTIFY_TITLE, f"Music CD: {job.label} {PROCESS_COMPLETE}")
            utils.scan_emby(job)
            # This shouldnt be needed. but to be safe
            job.status = "success"
            dbutil.commit()
            job.eject()
        else:
            logging.info("Music rip failed.  See previous errors.  Exiting. ")
            job.eject()
            job.status = "fail"
            dbutil.commit()

    elif job.disctype == "data":
        # get filesystem in order
        datapath = os.path.join(cfg.get("DATA_PATH", cfg["RAW_PATH"]), str(job.label))
        if (fs_utils.make_dir(datapath)) is False:
            ts = str(round(time.time() * 100))
            datapath = os.path.join(cfg.get("DATA_PATH", cfg["RAW_PATH"]), str(job.label) + "_" + ts)

            if (fs_utils.make_dir(datapath)) is False:
                logging.info(f"Could not create data directory: {datapath}  Exiting ARM. ")
                sys.exit()

        if utils.rip_data(job, datapath, logfile):
            utils.notify(job, NOTIFY_TITLE, f"Data disc: {job.label} copying complete. ")
        else:
            logging.info("Data rip failed.  See previous errors.  Exiting.")
        job.eject()

    else:
        logging.info("Couldn't identify the disc type. Exiting without any action.")

    # job.status = "success"
    # job.stop_time = datetime.datetime.now()
    # joblength = job.stop_time - job.start_time
    # minutes, seconds = divmod(joblength.seconds + joblength.days * 86400, 60)
    # hours, minutes = divmod(minutes, 60)
    # len = '{:d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
    # job.job_length = len
    # dbutil.commit()

def cli():
    """ cli entry point """
    args = parse_args()
    env_cfg = os.getenv("ARM_CONFIG_FILE", args.config_file)
    if env_cfg:
        cfg.path = args.config_file.format(hostname=platform.node(), devpath=args.devpath)
    arm.ui.configure_app()
    devpath = args.devpath
    if not os.path.exists(devpath):
        devpath = "/dev/" + args.devpath
    if args.wait:
        while 4 != utils.get_cdrom_status(devpath):
            time.sleep(10)
    
    job = Job(devpath)
    logfile = logger.setuplogging(job, level=args.log_level)
    log = logging.getLogger("arm")
    if utils.get_cdrom_status(devpath) != 4:
        logging.info("Drive appears to be empty or is not ready.  Exiting ARM.")
        sys.exit()
    # Dont put out anything if we are using the empty.log or NAS_
    if logfile.find("empty.log") != -1 or re.search("NAS_[0-9].?log", logfile) is not None:
        sys.exit()
    # This will kill any runs that have been triggered twice on the same device
    running_jobs = db.session.query(Job).filter(Job.status.notin_(['fail', 'success']), Job.devpath == devpath, Job.host == platform.node()).all()
    if len(running_jobs) >= 1:
        for j in running_jobs:
            print(j.start_time - datetime.datetime.now())
            z = int(round(abs(j.start_time - datetime.datetime.now()).total_seconds()) / 60)
            if z <= 1:
                logging.error(f"Job already running on {devpath}")
                sys.exit(1)

    logging.info("Starting ARM processing at %s", datetime.datetime.now())

    dbutil.check_db_version(cfg['INSTALLPATH'], cfg['DBFILE'], arm.ui.app)
    
    # put in db
    job.status = "active"
    job.start_time = datetime.datetime.now()
    utils.database_adder(job)

    time.sleep(1)
    config = Config(cfg, job_id=job.job_id)
    utils.database_adder(config)

    # Log version number
    version = arm.__version__
    logging.info(f"ARM version: {version}")
    job.arm_version = version
    logging.info(("Python version: " + sys.version).replace('\n', ""))
    logging.info(f"User is: {getpass.getuser()}")
    logger.clean_up_logs(cfg["LOGPATH"], cfg["LOGLIFE"])
    logging.info(f"Job: {job.label}")
    utils.clean_old_jobs()
    log_udev_params(devpath)

    try:
        main(logfile, job)
    except Exception as e:
        logging.exception("A fatal error has occurred and ARM is exiting.  See traceback below for details.")
        utils.notify(job, NOTIFY_TITLE, "ARM encountered a fatal error processing "
                                        f"{job.title}. Check the logs for more details. {e}")
        job.status = "fail"
        job.eject()
    else:
        job.status = "success"
    finally:
        job.stop_time = datetime.datetime.now()
        joblength = job.stop_time - job.start_time
        minutes, seconds = divmod(joblength.seconds + joblength.days * 86400, 60)
        hours, minutes = divmod(minutes, 60)
        total_len = '{:d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
        job.job_length = total_len
        dbutil.commit()

if __name__ == "__main__":
    cli()
