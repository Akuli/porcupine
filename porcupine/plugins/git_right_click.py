"""Add "git add" and some other options to the right-click menu in directory tree."""
from __future__ import annotations

import logging
import subprocess
import tkinter

from porcupine import utils
from porcupine.plugins.directory_tree import DirectoryTree, get_directory_tree, get_path

setup_after = ["directory_tree", "filemanager"]

log = logging.getLogger(__name__)


def run(command: list[str]) -> None:
    log.info(f"running command: {command}")
    try:
        subprocess.check_call(command, **utils.subprocess_kwargs)
    except (OSError, subprocess.CalledProcessError):
        log.exception(f"git command failed: {command}")


def populate_menu(event: tkinter.Event[DirectoryTree]) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)
    project_root = get_path(tree.find_project_id(item))

    try:
        subprocess.check_call(
            ["git", "status"],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            **utils.subprocess_kwargs,
        )
    except (OSError, subprocess.CalledProcessError):
        return

    if tree.contextmenu.index("end") is not None:  # menu not empty
        tree.contextmenu.add_separator()

    # Some git commands are different than what label shows, for compatibility with older git versions
    tree.contextmenu.add_command(
        label="git add", command=(lambda: run(["git", "add", "--", str(path)]))
    )
    tree.contextmenu.add_command(
        label="git restore --staged (undo add)",
        command=(lambda: run(["git", "reset", "HEAD", "--", str(path)])),
    )
    tree.contextmenu.add_command(
        label="git restore (discard non-added changes)",
        command=(lambda: run(["git", "checkout", "--", str(path)])),
    )


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", populate_menu, add=True)
