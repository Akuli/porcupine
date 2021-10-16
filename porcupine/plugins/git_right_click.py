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


def run(command: list[str], path: Path) -> None:
    log.info(f"running command: {command}")
    try:
        subprocess.check_call(command, cwd=path, **utils.subprocess_kwargs)
    except (OSError, subprocess.CalledProcessError):
        log.exception(f"git command failed: {command}")
    get_tab_manager().event_generate("<<FileSystemChanged>>")


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

    # Commands can be different than what label shows, for compatibility with older gits
    # Relies on git_status plugin
    tree.contextmenu.add_command(
        label="git add",
        command=(lambda: run(["git", "add", "--", str(path)], path.parent)),
        state=("normal" if tree.tag_has("git_modified", item) else "disabled"),
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
