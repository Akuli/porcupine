import itertools
import logging
import os
import pathlib
import platform
import shlex
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from typing import Any, List, TextIO, cast

import porcupine
from porcupine import dirs

log = logging.getLogger(__name__)
FILENAME_FIRST_PART_FORMAT = '%Y-%m-%dT%H-%M-%S'

# might be useful to grep something from old logs, but 30 days was way too much
LOG_MAX_AGE_DAYS = 7


# tests monkeypatch dirs.cachedir
def get_log_dir() -> pathlib.Path:
    return dirs.cachedir / 'logs'


def _remove_old_logs() -> None:
    for path in get_log_dir().glob('*.txt'):
        # support '<log dir>/<first_part>_<number>.txt' and '<log dir>/<firstpart>.txt'
        first_part = path.stem.split('_')[0]
        try:
            log_date = datetime.strptime(first_part, FILENAME_FIRST_PART_FORMAT)
        except ValueError:
            log.info(f"{path.parent} contains a file with an unexpected name: {path.name}")
            continue

        how_old = datetime.now() - log_date
        if how_old > timedelta(days=LOG_MAX_AGE_DAYS):
            log.info(f"{path} is more than {LOG_MAX_AGE_DAYS} days old, removing")
            path.unlink()


def _run_command(command: str) -> None:
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


def _open_log_file() -> TextIO:
    get_log_dir().mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime(FILENAME_FIRST_PART_FORMAT)
    filenames = (
        f'{timestamp}.txt' if i == 0 else f'{timestamp}_{i}.txt'
        for i in itertools.count()
    )
    for filename in filenames:
        try:
            return (get_log_dir() / filename).open('x', encoding='utf-8')
        except FileExistsError:
            continue
    assert False  # makes mypy happy


def setup(verbose: bool) -> None:
    handlers: List[logging.Handler] = []

    log_file = _open_log_file()
    file_handler = logging.StreamHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(name)s %(levelname)s: %(message)s'))
    handlers.append(file_handler)

    if sys.stderr is not None:
        # not running in pythonw.exe, can also show something in terminal
        print_handler = logging.StreamHandler(sys.stderr)
        print_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
        print_handler.setFormatter(logging.Formatter(
            '%(name)s %(levelname)s: %(message)s'))
        handlers.append(print_handler)

    # don't know why level must be specified here
    logging.basicConfig(level=logging.DEBUG, handlers=handlers)

    log.debug("starting Porcupine %s from '%s'", porcupine.__version__,
              cast(Any, porcupine).__path__[0])
    log.debug("log file: %s", log_file.name)
    if not verbose:
        print(f"log file: {log_file.name}")
    log.debug("PID: %d", os.getpid())
    log.debug("running on Python %d.%d.%d from '%s'",
              *sys.version_info[:3], sys.executable)
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
