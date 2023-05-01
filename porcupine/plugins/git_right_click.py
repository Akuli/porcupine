"""Add "git add" and some other options to the right-click menu in directory tree."""
from __future__ import annotations

import logging
import subprocess
import tkinter
from pathlib import Path
from tkinter import messagebox

from porcupine import get_tab_manager, utils
from porcupine.plugins.directory_tree import DirectoryTree, get_directory_tree, get_path

setup_after = ["directory_tree", "filemanager"]

log = logging.getLogger(__name__)

# for parsing output of "git status --porcelain"
# There are many other characters, but they all seem to indicate some kind of change.
UNTRACKED = "?"
NOTHING_CHANGED = " "


def run(command: list[str], cwd: Path) -> None:
    if command[1] == "checkout":
        if messagebox.askyesno(
            f"Git Action Requires Action",
            "Do you really want to perform this action?",
            icon="warning",
        ):
            log.info(f"running command: {command}")
            try:
                subprocess.check_call(command, cwd=cwd, **utils.subprocess_kwargs)
            except (OSError, subprocess.CalledProcessError):
                log.exception(f"git command failed: {command}")
            get_tab_manager().event_generate("<<FileSystemChanged>>")
    else:
        log.info(f"running command: {command}")
        try:
            subprocess.check_call(command, cwd=cwd, **utils.subprocess_kwargs)
        except (OSError, subprocess.CalledProcessError):
            log.exception(f"git command failed: {command}")
        get_tab_manager().event_generate("<<FileSystemChanged>>")


def populate_menu(event: tkinter.Event[DirectoryTree]) -> None:
    tree: DirectoryTree = event.widget
    try:
        [item] = tree.selection()
    except ValueError:
        return

    path = get_path(item)

    if path is None:
        return

    if path.is_dir():
        git_cwd = path
    else:
        git_cwd = path.parent

    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain", "--", str(path)],
            cwd=git_cwd,
            **utils.subprocess_kwargs,
        )
    except (OSError, subprocess.CalledProcessError):
        return
    staged_states = [line[0:1].decode("ascii") for line in output.splitlines()]
    unstaged_states = [line[1:2].decode("ascii") for line in output.splitlines()]

    if tree.contextmenu.index("end") is not None:  # menu not empty
        tree.contextmenu.add_separator()

    # Commands can be different than what label shows, for compatibility with older gits
    tree.contextmenu.add_command(
        label="git add",
        command=(lambda: run(["git", "add", "--", str(path)], git_cwd)),
        state=("normal" if any(s != NOTHING_CHANGED for s in unstaged_states) else "disabled"),
    )
    tree.contextmenu.add_command(
        label="git restore --staged (undo add)",
        command=(lambda: run(["git", "reset", "HEAD", "--", str(path)], git_cwd)),
        state=(
            "normal"
            if any(s not in {NOTHING_CHANGED, UNTRACKED} for s in staged_states)
            else "disabled"
        ),
    )
    tree.contextmenu.add_command(
        label="git restore (discard non-added changes)",
        command=(lambda: run(["git", "checkout", "--", str(path)], git_cwd)),
        state=(
            "normal"
            if any(s not in {NOTHING_CHANGED, UNTRACKED} for s in unstaged_states)
            else "disabled"
        ),
    )


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", populate_menu, add=True)
