"""Add "git add" and some other options to the right-click menu in directory tree."""
from __future__ import annotations

import logging
import subprocess
import tkinter
from pathlib import Path

from porcupine import get_tab_manager, utils
from porcupine.plugins.directory_tree import DirectoryTree, get_directory_tree, get_path

setup_after = ["directory_tree", "filemanager"]

log = logging.getLogger(__name__)

# for parsing output of "git status --porcelain"
# There are many other characters, but they all seem to indicate some kind of change.
UNTRACKED = "?"
NOTHING_CHANGED = " "


def run(command: list[str], cwd: Path) -> None:
    log.info(f"running command: {command}")
    try:
        subprocess.check_call(command, cwd=cwd, **utils.subprocess_kwargs)
    except (OSError, subprocess.CalledProcessError):
        log.exception(f"git command failed: {command}")
    get_tab_manager().event_generate("<<FileSystemChanged>>")


def populate_menu(event: tkinter.Event[DirectoryTree]) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)

    try:
        output = subprocess.check_output(['git', 'status', '--porcelain', '--', str(path)], cwd=path.parent, **utils.subprocess_kwargs)
    except (OSError, subprocess.CalledProcessError):
        return
    tracked_statuses = [line[0:1].decode("ascii") for line in output.splitlines()]
    untracked_statuses = [line[1:2].decode("ascii") for line in output.splitlines()]

    if tree.contextmenu.index("end") is not None:  # menu not empty
        tree.contextmenu.add_separator()

    # Commands can be different than what label shows, for compatibility with older gits
    # Relies on git_status plugin
    tree.contextmenu.add_command(
        label="git add",
        command=(lambda: run(["git", "add", "--", str(path)], path.parent)),
        state="disabled" if all(s == NOTHING_CHANGED for s in untracked_statuses) else "normal",
    )
    tree.contextmenu.add_command(
        label="git restore --staged (undo add)",
        command=(lambda: run(["git", "reset", "HEAD", "--", str(path)], path.parent)),
        # TODO: disable this reasonably
        # currently git_added tag missing if there is git_modified tag
    )
    tree.contextmenu.add_command(
        label="git restore (discard non-added changes)",
        command=(lambda: run(["git", "checkout", "--", str(path)], path.parent)),
        state=("normal" if tree.tag_has("git_modified", item) else "disabled"),
    )


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", populate_menu, add=True)
