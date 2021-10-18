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

    if path.is_dir():
        git_cwd = path
    else:
        git_cwd = path.parent

    try:
        output = subprocess.check_output(['git', 'status', '--porcelain', '--', str(path)], cwd=git_cwd, **utils.subprocess_kwargs)
    except (OSError, subprocess.CalledProcessError):
        return
    staged_changes = [line[0:1].decode("ascii") for line in output.splitlines()]
    unstaged_changes = [line[1:2].decode("ascii") for line in output.splitlines()]

    if tree.contextmenu.index("end") is not None:  # menu not empty
        tree.contextmenu.add_separator()

    # Commands can be different than what label shows, for compatibility with older gits
    # TODO: use git_cwd here
    tree.contextmenu.add_command(
        label="git add",
        command=(lambda: run(["git", "add", "--", str(path)], path.parent)),
        state=("normal" if any(s != NOTHING_CHANGED for s in unstaged_changes) else "disabled"),
    )
    tree.contextmenu.add_command(
        label="git restore --staged (undo add)",
        command=(lambda: run(["git", "reset", "HEAD", "--", str(path)], path.parent)),
        state="normal" if any(s not in {NOTHING_CHANGED, UNTRACKED} for s in staged_changes) else "disabled",
    )
    tree.contextmenu.add_command(
        label="git restore (discard non-added changes)",
        command=(lambda: run(["git", "checkout", "--", str(path)], path.parent)),
        state=("normal" if any(s not in {NOTHING_CHANGED, UNTRACKED} for s in unstaged_changes) else "disabled"),
    )


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", populate_menu, add=True)
