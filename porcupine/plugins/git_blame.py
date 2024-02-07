from __future__ import annotations

import datetime
import logging
import re
import subprocess
import sys
import time
import tkinter
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import NamedTuple

from porcupine import get_tab_manager, tabs, utils
from porcupine.plugins.statusbar import get_statusbar

log = logging.getLogger(__name__)

GIT_BLAME_REGEX = r"([0-9a-fA-F]+)\s\((.+?)\s([0-9]*)\s.{5}\s[0-9]+\)"
setup_after = ["statusbar"]


class Commit(NamedTuple):
    hash: str
    author: str
    date: datetime.datetime
    message: str


def prettify_date(date: datetime.datetime) -> str:
    diff = datetime.datetime.now() - date
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        # In the future
        return ""
    elif day_diff == 0:
        if second_diff < 60:
            return f"{second_diff} seconds ago"
        elif second_diff < 120:
            return "a minute ago"
        elif second_diff < 3600:
            return f"{second_diff // 60} minutes ago"
        elif second_diff < 7200:
            return "an hour ago"
        elif second_diff < 24 * 3600:
            return f"{second_diff // 3600} hours ago"
    elif day_diff == 1:
        return "Yesterday"
    elif day_diff < 7:
        return f"{day_diff} days ago"
    elif day_diff < 31:
        return f"{day_diff // 7} weeks ago"
    elif day_diff < 365:
        return f"{day_diff // 30} months ago"

    return f"{day_diff // 365} years ago"


def run_git(*args, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        capture_output=True,
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

    hash, author, timestamp = result.groups()
    date = datetime.datetime.fromtimestamp(int(timestamp))
    message = run_git("log", "-n", "1", "--pretty=format:%s", hash, cwd=path.parent).stdout

    return Commit(hash, author, date, message)


def show_git_blame(path: Path, widget: ttk.Label, event: tkinter.Event[tkinter.Text]) -> None:
    # FIXME: don't abuse git when editing on the same line

    if event.widget.tag_ranges("sel"):
        # TODO: Why is this not working?
        return
    line_num = int(event.widget.index("insert").split(".")[0])

    commit = git_blame_get_commit(path=path, line=line_num)
    if commit is None:
        return

    if all(c == "0" for c in commit.hash):
        formatted = f";  not committed yet"
    else:
        formatted = f";  changed by {commit.author} {prettify_date(commit.date)} • {commit.message}"
    widget.configure(text=formatted)


def on_new_filetab(tab: tabs.FileTab) -> None:
    statusbar = get_statusbar(tab)
    if statusbar is None or not tab.path or not is_in_git_repo(tab.path):
        return

    widget = ttk.Label(statusbar)
    widget.pack(side="left", padx=(1, 5))
    tab.textwidget.bind("<<CursorMoved>>", partial(show_git_blame, tab.path, widget), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
