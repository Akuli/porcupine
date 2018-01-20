import glob
import itertools
import logging
import os
import platform
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


# running lsb_release takes about 0.12 seconds on this system => thread it :DDD
# no really i want things to start up as quickly as possible and logging
# is thread-safe so why not
def _run_lsb_release():
    try:
        output = subprocess.check_output(['lsb_release', '-a'],
                                         stderr=subprocess.STDOUT)
        log.info("output from 'lsb_release -a':\n%s",
                 output.decode('utf-8', errors='replace'))
    except (subprocess.CalledProcessError, OSError):
        log.warning("unexpected error when calling lsb_release", exc_info=True)


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

    log.info("starting Porcupine %s from '%s'", porcupine.__version__,
             porcupine.__path__[0])
    log.info("PID %d, log file '%s'", os.getpid(), logfile_path)
    log.info("running on Python %d.%d.%d from '%s'",
             *(list(sys.version_info[:3]) + [sys.executable]))
    log.info("platform.system() returned %r", platform.system())
    if shutil.which('lsb_release') is not None:
        threading.Thread(target=_run_lsb_release).start()
    else:   # e.g. windows
        log.info("platform.platform() returned %r", platform.platform())

    # don't fail to run if old logs can't be deleted for some reason
    try:
        _remove_old_logs()
    except OSError:
        log.exception("unexpected problem with removing old log files")
