from setuptools import setup, find_packages
from os.path import join, isfile
import glob
import re

def globm(*args, exclude=set()):
    """ glob multiple patterns"""
    r = []
    exclude = [ re.compile(x) for x in exclude]
    for a in args:
        r.extend([ x for x in glob.glob(a) if len([True for z in exclude if z.match(x)]) == 0])
    return r
                 
setup(
    name='arm',
    version='2.5.2',
    packages=find_packages(include=['arm', 'arm.*']),
    url='https://github.com/automatic-ripping-machine/automatic-ripping-machine',
    license='MIT',
    install_requires=[
        'pydvdid>=1.0',
        'requests>=2.9.1',
        'xmltodict>=0.10.2',
        'pyudev>=0.21.0',
        'pyyaml>=3.12',
        'flask>=1.0.2',
        'flask-WTF>=0.14.2',
        'flask-sqlalchemy>=2.3.2',
        'flask-migrate>=2.2.1',
        'omdb>=0.10.0',
        'psutil>=5.4.6',
        'robobrowser>=0.5.3',
        'tinydownload>=0.1.0',
        'netifaces>=0.10.9',
        'flask-login>=0.5.0',
        'apprise>=0.8.9',
        'musicbrainzngs>=0.7.1',
        'discid>=1.1.1',
        'psutil',
        'flask_cors',
        'bcrypt',
        'prettytable',
        'psycopg2',
    ],
    tests_require=(),
    options={},
    scripts=['scripts/arm_wrapper.sh', 'scripts/deb-install-quiet.sh', 'scripts/debian-setup.sh'],
    description=('Automatic Ripping Machine (ARM) - Automated DVD/BlueRay backup'),
    long_description=(
        """
        The A.R.M. (Automatic Ripping Machine) detects the insertion of an optical disc, 
        identifies the type of media and autonomously performs the appropriate action:

        DVD / Blu-ray -> Rip with MakeMKV and Transcode with Handbrake
        Audio CD -> Rip and Encode to FLAC and Tag the files if possible.
        Data Disc -> Make an ISO backup
        """
    ),
    package_data={
        'arm.ui': ['templates/*', 'static/*/*', 'static/manifest.json', '*.json'],
        'arm.migrations': ['alembic.ini', 'script.py.mako', 'versions/*'],
    },

    # Package data: MANIFEST.in
    data_files=[
        ('share/doc/arm', globm('docs/*', 'setup/*', exclude=["PSDs"])),
        ('share/doc/arm-scripts', globm('scripts/*', exclude=[".*\.app"])),
    ],  # Optional
    entry_points={'console_scripts': [
        'arm = arm.ripper.main:cli',
        'arm-ui = arm.runui:main'
    ]},

    # Files that can be tinkered by the user
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'])
