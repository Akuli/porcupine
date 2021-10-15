from __future__ import annotations

import itertools
import logging
import os
import shlex
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TextIO, cast

import porcupine
from porcupine import dirs

log = logging.getLogger(__name__)
FILENAME_FIRST_PART_FORMAT = "%Y-%m-%dT%H-%M-%S"

# might be useful to grep something from old logs, but 30 days was way too much
LOG_MAX_AGE_DAYS = 7


def _remove_old_logs() -> None:
    for path in Path(dirs.user_log_dir).glob("*.txt"):
        # support '<log dir>/<first_part>_<number>.txt' and '<log dir>/<firstpart>.txt'
        first_part = path.stem.split("_")[0]
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
        output = subprocess.check_output(shlex.split(command), stderr=subprocess.STDOUT).decode(
            "utf-8", errors="replace"
        )
        log.info(f"output from '{command}':\n{output}")
    except FileNotFoundError as e:
        log.info(f"cannot run '{command}': {e}")
    except (subprocess.CalledProcessError, OSError):
        log.warning(f"unexpected error when running '{command}'", exc_info=True)


def _open_log_file() -> TextIO:
    timestamp = datetime.now().strftime(FILENAME_FIRST_PART_FORMAT)
    filenames = (
        f"{timestamp}.txt" if i == 0 else f"{timestamp}_{i}.txt" for i in itertools.count()
    )
    for filename in filenames:
        try:
            return (Path(dirs.user_log_dir) / filename).open("x", encoding="utf-8")
        except FileExistsError:
            continue
    assert False  # makes mypy happy


class _FilterThatDoesntHideWarnings(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING or super().filter(record)


# verbose_logger can be:
#   - empty string (print everything)
#   - logger name (print only messages from that logger)
#   - None (only print errors)
def setup(verbose_logger: str | None) -> None:
    handlers: list[logging.Handler] = []

    log_file = _open_log_file()
    print(f"log file: {log_file.name}")

    file_handler = logging.StreamHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s")
    )
    handlers.append(file_handler)

    if sys.stderr is not None:
        # not running in pythonw.exe, can also show something in terminal
        print_handler = logging.StreamHandler(sys.stderr)
        if verbose_logger is None:
            print_handler.setLevel(logging.WARNING)
        else:
            print_handler.setLevel(logging.DEBUG)
            print_handler.addFilter(_FilterThatDoesntHideWarnings(verbose_logger))
        print_handler.setFormatter(logging.Formatter("%(name)s %(levelname)s: %(message)s"))
        handlers.append(print_handler)

    # don't know why level must be specified here
    logging.basicConfig(level=logging.DEBUG, handlers=handlers)

    porcupine_path = cast(Any, porcupine).__path__[0]
    log.debug(f"starting Porcupine {porcupine.__version__} from '{porcupine_path}'")
    log.debug(f"PID: {os.getpid()}")
    log.debug("running on Python %d.%d.%d from '%s'", *sys.version_info[:3], sys.executable)
    log.debug(f"sys.platform is {sys.platform!r}")
    if sys.platform != "win32":
        # lsb_release is a python script on ubuntu so running it takes
        # about 0.12 seconds on this system, i really want porcupine to
        # start as fast as possible
        _run_command("uname -a")
        threading.Thread(target=_run_command, args=["lsb_release -a"]).start()

    # don't fail to run if old logs can't be deleted for some reason
    try:
        _remove_old_logs()
    except OSError:
        log.exception("unexpected problem with removing old log files")
