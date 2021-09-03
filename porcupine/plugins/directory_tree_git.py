from __future__ import annotations

import subprocess
import logging
import sys
from functools import partial
from pathlib import Path

from porcupine import get_paned_window, utils
from porcupine.plugins.directory_tree import DirectoryTree, get_path

setup_after = ["directory_tree", "directory_tree_delete"]
log = logging.getLogger(__name__)

if sys.platform == "win32":
    trash_name = "recycle bin"
else:
    trash_name = "trash"


def git(*command: str | Path):
    log.info(f"running git command: {command}")
    try:
        subprocess.check_call(["git"] + list(command), **utils.subprocess_kwargs)
    except (OSError, subprocess.CalledProcessError):
        log.exception(f"git command failed: {command}")


def populate_menu(event) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)
    project_root = get_path(tree.find_project_id(item))

    run_result = subprocess.run(
        ["git", "status"], cwd=project_root, stdout=subprocess.DEVNULL, **utils.subprocess_kwargs
    )
    if run_result.returncode == 0:
        if tree.contextmenu.index("end") is not None:  # not empty
            tree.contextmenu.add_separator()

        # Some git commands are different than what label shows, for compatibility with older git versions
        tree.contextmenu.add_command(label="git add", command=partial(git, "add", "--", path))
        tree.contextmenu.add_command(
            label="git restore --staged (undo git add)",
            command=partial(git, "reset", "HEAD", "--", path),
        )
        tree.contextmenu.add_command(
            label="git restore (discard non-added changes)",
            command=partial(git, "checkout", "--", path),
        )


def setup() -> None:
    for widget in utils.get_children_recursively(get_paned_window()):
        if isinstance(widget, DirectoryTree):
            utils.bind_with_data(widget, "<<PopulateContextMenu>>", populate_menu, add=True)
