
import os
import logging
import shutil
import sys
from arm.ui import db
from arm.ripper.fs_utils import make_dir
from time import strftime, localtime, time

# currently defer to arm.ui db, allow to migrate the different part to a db interface separate from ui


def check_db_version(install_path, db_file, app):
    """
    Check if db exists and is up to date.
    If it doesn't exist create it.  If it's out of date update it.
    """
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    import sqlite3
    import flask_migrate
    import arm.migrations

    config = Config()
    
    mig_dir= os.path.dirname(sys.modules["arm.migrations"].__file__)

    config.set_main_option("script_location", mig_dir)
    script = ScriptDirectory.from_config(config)

    # create db file if it doesn't exist
    if not os.path.isfile(db_file):
        logging.info("No database found.  Initializing arm.db...")
        make_dir(os.path.dirname(db_file))
        with app.app_context():
            flask_migrate.upgrade(mig_dir)

        if not os.path.isfile(db_file):
            logging.debug("Can't create database file.  This could be a permissions issue.  Exiting...")

    # check to see if db is at current revision
    head_revision = script.get_current_head()
    logging.debug("Head is: %s", head_revision)

    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    c.execute("SELECT {cn} FROM {tn}".format(cn="version_num", tn="alembic_version"))
    if not c.fetchone():
        return
    db_version = c.fetchone()[0]
    logging.debug("Database version is: " + db_version)
    if head_revision == db_version:
        logging.info("Database is up to date")
    else:
        logging.info(
            "Database out of date. Head is " + head_revision + " and database is " + db_version
            + ".  Upgrading database...")
        with app.app_context():
            ts = round(time() * 100)
            logging.info("Backuping up database '" + db_file + "' to '" + db_file + str(ts) + "'.")
            shutil.copy(db_file, db_file + "_" + str(ts))
            flask_migrate.upgrade(mig_dir)
        logging.info("Upgrade complete.  Validating version level...")

        c.execute("SELECT {cn} FROM {tn}".format(tn="alembic_version", cn="version_num"))
        db_version = c.fetchone()[0]
        logging.debug("Database version is: " + db_version)
        if head_revision == db_version:
            logging.info("Database is now up to date")
        else:
            logging.error(
                "Database is still out of date. Head is " + head_revision + " and database is " + db_version
                + ".  Exiting arm.")
            # sys.exit()

def commit():
    """ wrapper, for exceptions"""
    try:
        db.session.commit()
    except Exception as e:
        logging.warning("Database commit error %s", e)
    
