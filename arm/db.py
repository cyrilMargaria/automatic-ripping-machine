
import os
import logging
import shutil
import sys
from arm.ui import db
from arm.ripper.fs_utils import make_dir
from time import strftime, localtime, time

# currently defer to arm.ui db, allow to migrate the different part to a db interface separate from ui


def get_db_version():
    """ Return db schema version """
    c = db.session.execute("SELECT {cn} FROM {tn}".format(cn="version_num", tn="alembic_version"))
    entry = c.fetchone()
    if entry:
        return entry[0]
    return ""


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
    import arm.config.config 
    config = Config()
    
    mig_dir= os.path.dirname(sys.modules["arm.migrations"].__file__)

    config.set_main_option("script_location", mig_dir)
    script = ScriptDirectory.from_config(config)

    # check if alembic_version exists
    inspector = db.inspect(db.engine)
    created = "alembic_version" in inspector.get_table_names()
    
    # create db file if it doesn't exist
    if not created:
        logging.info("No database found.  Initializing arm.db...")
        if inspector.dialect.driver == "sqlite":
            make_dir(os.path.dirname(db_file))
        with app.app_context():
            flask_migrate.upgrade(mig_dir)
        inspector = db.inspect(db.engine)
        created = "alembic_version" in inspector.get_table_names()
        if not created:
            logging.debug("Can't create database file.  This could be a permissions issue.  Exiting...")
    
    # check to see if db is at current revision
    head_revision = script.get_current_head()
    logging.debug("Head is: %s", head_revision)
    
    # conn = sqlite3.connect(db_file)
    # c = conn.cursor()
    db_version = get_db_version()
    logging.debug("Database version is: %s", db_version)
    if head_revision == db_version:
        logging.info("Database is up to date")
    else:
        logging.info(
            "Database out of date. Head is %s  and database is %s.  Upgrading database...",
            head_revision, db_version)
        with app.app_context():
            ts = round(time() * 100)
            if inspector.dialect.driver == "sqlite":
                backup_file = f"{db_file}_{ts}"
                logging.info("Backuping up database '%s' to '%s'", db_file, backup_file)
                shutil.copy(db_file, backup_file)
            flask_migrate.upgrade(mig_dir)
        logging.info("Upgrade complete.  Validating version level...")

        db_version = get_db_version()
        logging.debug("Database version is: %s", db_version)
        if head_revision == db_version:
            logging.info("Database is now up to date")
        else:
            logging.error(
                "Database is still out of date. Head is %s and database is %s.  Exiting arm.",
                head_revision, db_version)
            # sys.exit()

def commit():
    """ wrapper, for exceptions"""
    try:
        db.session.commit()
    except Exception as e:
        logging.warning("Database commit error %s", e)
    
