import glob
import itertools
import logging
import os
import platform
import shlex
import shutil
import subprocess
import sys
import threading
import time

import porcupine
from porcupine import dirs

log = logging.getLogger(__name__)
DAYS = 60*60*24       # seconds in 1 day


def _remove_old_logs():
    pattern = os.path.join(glob.escape(dirs.cachedir), 'log*.txt')
    for filename in glob.glob(pattern):
        path = os.path.join(dirs.cachedir, filename)
        if time.time() - os.path.getmtime(path) > 3*DAYS:
            log.info("'%s' is more than 3 days old, removing it")
            os.remove(path)


def _run_command(command):
    try:
        output = subprocess.check_output(shlex.split(command),
                                         stderr=subprocess.STDOUT)
        log.info("output from '%s':\n%s", command,
                 output.decode('utf-8', errors='replace'))
    except FileNotFoundError as e:
        log.info("cannot run '%s': %s", command, e)
    except (subprocess.CalledProcessError, OSError):
        log.warning("unexpected error when running '%s'", command,
                    exc_info=True)


def setup(verbose):
    print_handler = logging.StreamHandler(sys.stderr)
    print_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)

    # an iterator 'log.txt', 'log2.txt', 'log3.txt', ...
    filenames = itertools.chain(
        ['log.txt'],
        map('log{}.txt'.format, itertools.count(start=2)),
    )
    for filename in filenames:
        logfile_path = os.path.join(dirs.cachedir, filename)
        try:
            # x means create without overwriting
            file_handler = logging.FileHandler(logfile_path, 'x')
        except FileExistsError:
            continue
        file_handler.setLevel(logging.DEBUG)
        break

    logging.basicConfig(level=logging.DEBUG,  # no idea why this is needed
                        handlers=[print_handler, file_handler],
                        format="[%(levelname)s] %(name)s: %(message)s")

    log.debug("starting Porcupine %s from '%s'", porcupine.__version__,
              porcupine.__path__[0])
    log.debug("PID %d, log file '%s'", os.getpid(), logfile_path)
    log.debug("running on Python %d.%d.%d from '%s'",
              *(list(sys.version_info[:3]) + [sys.executable]))
    log.debug("platform.system() returned %r", platform.system())
    log.debug("platform.platform() returned %r", platform.platform())
    if platform.system() != 'Windows':
        # lsb_release is a python script on ubuntu so running it takes
        # about 0.12 seconds on this system, i really want porcupine to
        # start as fast as possible
        _run_command('uname -a')
        threading.Thread(target=_run_command, args=['lsb_release -a']).start()

    # don't fail to run if old logs can't be deleted for some reason
    try:
        _remove_old_logs()
    except OSError:
        log.exception("unexpected problem with removing old log files")
