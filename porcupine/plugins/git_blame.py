from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import NamedTuple

from porcupine import get_tab_manager, utils

log = logging.getLogger(__name__)

GIT_BLAME_REGEX = r"([0-9a-fA-F]+)\s\((.+?)\s([0-9]*)\s.{5}\s[0-9]+\)"


class Commit(NamedTuple):
    revision: int
    message: str
    author: str
    date: datetime


def run_git(*args, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding=sys.getfilesystemencoding(),
        timeout=(60 * 10),  # 10min. Must be huge to avoid unnecessary killing (#885)
        **utils.subprocess_kwargs,
    )


def is_in_git_repo(path: Path) -> bool:
    for parent in path.parents:
        if (parent / ".git").is_dir():
            return True
    return False


def git_blame_get_commit(path: Path, line: int) -> Commit | None:
    if not path or not is_in_git_repo(path):
        # TODO: Do we have to run this every time?
        return None

    try:
        start = time.perf_counter()
        git_blame_result = run_git(
            "blame", str(path), "-L", f"{line},{line}", "-t", cwd=path.parent
        )
        log.debug(
            f"running git blame for {path} took" f" {round((time.perf_counter() - start)*1000)}ms"
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        log.warning("can't run git", exc_info=True)
        return None

    result = re.search(GIT_BLAME_REGEX, git_blame_result.stdout)
    if not result:
        return None

    revision, author, timestamp = result.groups()
    date = datetime.fromtimestamp(int(timestamp))

    git_log_result = run_git("log", "-n", "1", "--pretty=format:%s", revision, cwd=path.parent)

    return Commit(revision, git_log_result.stdout, author, date)


def show_git_blame_message(path: Path, event) -> None:
    line_num = int(event.widget.index("insert").split(".")[0])

    res = git_blame_get_commit(path=path, line=line_num)
    if res is None:
        return

    formatted = f"Line {line_num}: by {res.author} at {res.date} - {res.message}"
    print(formatted)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.textwidget.bind("<<CursorMoved>>", partial(show_git_blame_message, tab.path), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
