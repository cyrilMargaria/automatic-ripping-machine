import os.path
import ctypes
import ctypes.util
import collections
import platform
import logging
from arm.config.config import cfg

OSX_MOUNT_TO_TYPE = {
    "udf": "dvd",
    "cddafs": "music",
    "cd9660": "data",
}

# POSIX
libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)

if platform.system() == 'Linux':
    import pyudev


def get_device_mount_point(device):
    """
       returns the device mount point, fs type, and true/false to
       indicate if the device is mounted.
    """
    # TODO: linux
    if platform.system() == 'Darwin':
        mounts = list_mounts_darwin()
        logging.debug("Mounts: %r", mounts)
        for mnt in mounts:
            if mnt.src == device:
                return mnt.dst, mnt.fs_type, mnt.fs_uuid, True
        return None, None, None, False
    # TODO: linux
    if platform.system() == 'Linux':
        mount = os.path.join(cfg.get("MOUNTPATH", "/mnt"), os.path.basename(device))
        # TODOq
    raise ValueError("Not implemented")


def get_device_info(devpath):
    """
     Parse udev/mount for properties of a given device returns the mount point,
     disk label and disc type
    """

    mount = None
    disctype = "unknown"
    label = ""
    if platform.system() == 'Darwin':
        mount, fs_type, uuid, _ = get_device_mount_point(devpath)
        if not mount:
            return mount, label, disctype
        disctype = OSX_MOUNT_TO_TYPE.get(fs_type, "unknown")
        label = "{}-{}".format(os.path.basename(mount), uuid)
        return mount, label, disctype
    # linux/default
    mount = os.path.join(cfg.get("MOUNTPATH", "/mnt"), devpath)
    # print("Entering disc")
    context = pyudev.Context()
    device = pyudev.Devices.from_device_file(context, devpath)
    for key, value in device.items():
        if key == "ID_FS_LABEL":
            label = value
        if value == "iso9660":
            disctype = "data"
        elif key == "ID_CDROM_MEDIA_BD":
            disctype = "bluray"
        elif key == "ID_CDROM_MEDIA_DVD":
            disctype = "dvd"
        elif key == "ID_CDROM_MEDIA_TRACK_COUNT_AUDIO":
            disctype = "music"
    return mount, label, disctype


def check_fstab():
    logging.info("Checking for fstab entry.")
    if platform.system() != 'Linux':
        return
    with open('/etc/fstab', 'r') as f:
        lines = f.readlines()
        for line in lines:
            # Now grabs the real uncommented fstab entry
            if re.search("^" + job.devpath, line):
                logging.info("fstab entry is: %s", line.rstrip())
                return
    logging.error("No fstab entry found.  ARM will likely fail.")


def check_device_path(devpath):
    """ return normalized device path """
    devpath = os.path.realpath(devpath)
    if not os.path.commonprefix(["/dev/", devpath]).startswith("/dev/"):
        raise ValueError(f"device must be under /dev :{devpath}")
    return devpath


def mount_device(devpath):
    """ Mount a device """
    logging.debug("mount %s", devpath)
    devpath = check_device_path(devpath)
    if platform.system() == 'Darwin':
        mount, fs_type, uuid, mounted = get_device_mount_point(devpath)
        if not mounted:
            logging.debug("not mounted, mount it %s", devpath)
            
            os.system(f"diskutil mount {devpath}")
        # we do not check?
    else:
        os.system("mount " + devpath)

def unmount_device(devpath):
    """ unmount a device """
    logging.debug("Unmount %s", devpath)
    devpath = check_device_path(devpath)
    if platform.system() == 'Darwin':
        mount, fs_type, uuid, mounted = get_device_mount_point(devpath)
        if mounted:
            os.system(f"diskutil unmountDisk {devpath}")
        # we do not check?
        pass
    else:
        os.system("umount " + devpath)


def eject_device(devpath):
    devpath = check_device_path(devpath)
    if platform.system() == 'Darwin':
        mount, fs_type, uuid, mounted = get_device_mount_point(devpath)
        if mounted:
            os.system(f"diskutil unmountDisk {devpath}")
        if os.system(f"diskutil eject {devpath} 0"):
            return True
        return os.system(f"drutil eject {devpath}")
    try:
        if os.system("umount " + devpath):
            logging.debug("we unmounted disc %s", devpath)
        if os.system("eject " + devpath):
            logging.debug("we ejected disc %s", devpath)
            return True
        logging.debug("failed to eject %s", devpath)
    except Exception as e:
        logging.debug("%s couldn't be ejected:%s ", devpath, e)
    return False


# for future use
def mount_fs(source, target, fs, options=''):
    ret = libc.mount(source.encode(), target.encode(), fs.encode(), 0, options.encode())
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"Error mounting {source} ({fs}) on {target} with options '{options}': {os.strerror(errno)}")


class FSEntry(ctypes.Structure):
    _fields_ = [
        ("fs_spec", ctypes.c_char_p),       # block device name
        ("fs_file", ctypes.c_char_p),       # mount point
        ("fs_vfstype", ctypes.c_char_p),    # filesystem type
        ("fs_mntops", ctypes.c_char_p),     # mount options
        ("fs_type", ctypes.c_char_p),       # rw/rq/ro/sw/xx option
        ("fs_freq", ctypes.c_int),          # dump frequency, in days
        ("fs_passno", ctypes.c_int),        # pass number on parallel dump
    ]

    def __str__(self):
        return f"dev={self.fs_spec.decode('ascii')} file={self.fs_file.decode('ascii')}"

def list_mounts():
    # POSIX
    libc.getfsent.restype = ctypes.POINTER(FSEntry)    
    libc.setfsent()
    while True:
        x = libc.getfsent()
        if not x:
            print("EOL")
            libc.endfsent()
            return
        print(str(x.contents))
    return


class fsid(ctypes.Structure):
    _pack_ = True  # source:False
    _fields_ = [("val", ctypes.c_int32 * 2)]


class StatFS(ctypes.Structure):
    _fields_ = [
        ("f_bsize", ctypes.c_uint32),           # fundamental file system block size */
        ("f_iosize", ctypes.c_int32),           # optimal transfer block size */
        ("f_blocks", ctypes.c_uint64),          # total data blocks in file system */
        ("f_bfree", ctypes.c_uint64),           # free blocks in fs */
        ("f_bavail", ctypes.c_uint64),          # free blocks avail to non-superuser */
        ("f_files", ctypes.c_uint64),           # total file nodes in file system */
        ("f_ffree", ctypes.c_uint64),           # free file nodes in fs */
        ("f_fsid", fsid),                       # file system id */
        ("f_owner", ctypes.c_uint32),           # user that mounted the filesystem */
        ("f_type", ctypes.c_uint32),            # type of filesystem */
        ("f_flags", ctypes.c_uint32),           # copy of mount exported flags */
        ("f_fssubtype", ctypes.c_uint32),       # fs sub-type (flavor) */
        ("f_fstypename", ctypes.c_char*16),     # fs type name */
        ("f_mntonname", ctypes.c_char*1024),    # directory on which mounted */
        ("f_mntfromname", ctypes.c_char*1024),  # mounted filesystem */
        ("f_reserved[8]", ctypes.c_uint32*8),   # For future use */
    ]


Mount = collections.namedtuple("Mount", "src dst fs_type fs_uuid")

if platform.system() == 'Darwin':
    try:
        getmntinfo = libc["getmntinfo$INODE64"]
    except (KeyError, AttributeError):
        getmntinfo = libc["getmntinfo"]

    getmntinfo.restype = ctypes.c_int
    getmntinfo.argtypes = (ctypes.POINTER(ctypes.POINTER(StatFS)), ctypes.c_int)

    def list_mounts_darwin():
        """ List currently mounted filesystems, return a list of Mount"""
        array = ctypes.POINTER(StatFS)()
        entries = getmntinfo(ctypes.byref(array), 2)
        return [Mount(
            array[x].f_mntfromname.decode('utf8'),
            array[x].f_mntonname.decode('utf8'),
            array[x].f_fstypename.decode('utf8'),
            "{:x}".format((array[x].f_fsid.val[0]<<32)|array[x].f_fsid.val[1])
        ) for x in range(0, entries)]


def make_dir(path):
    """
    Make a directory\n
    path = Path to directory\n

    returns success True if successful
        false if the directory already exists
    """
    if not os.path.exists(path):
        logging.debug(f"Creating directory: {path}")
        try:
            os.makedirs(path)
            return True
        except OSError:
            err = f"Couldn't create a directory at path: {path} Probably a permissions error.  Exiting"
            logging.error(err)
            sys.exit(err)
    else:
        return False
