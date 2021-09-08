"""File manager operations (delete, trash, rename, ...) when right-clicking directory tree."""
from __future__ import annotations

import logging
import shutil
import sys
import tkinter
from functools import partial
from pathlib import Path
from tkinter import messagebox

from send2trash import send2trash

from porcupine import get_tab_manager, tabs
from porcupine.plugins.directory_tree import DirectoryTree, get_directory_tree, get_path

setup_after = ["directory_tree"]
log = logging.getLogger(__name__)

if sys.platform == "win32":
    trash_name = "recycle bin"
else:
    trash_name = "trash"


def find_tabs_by_parent_path(path: Path) -> list[tabs.FileTab]:
    return [
        tab
        for tab in get_tab_manager().tabs()
        if isinstance(tab, tabs.FileTab)
        and tab.path is not None
        and (path == tab.path or path in tab.path.parents)
    ]


def close_tabs(tabs_to_close: list[tabs.FileTab]) -> bool:
    if not all(tab.can_be_closed() for tab in tabs_to_close):
        return False

    for tab in tabs_to_close:
        get_tab_manager().close_tab(tab)
    return True


def trash(path: Path) -> None:
    if not close_tabs(find_tabs_by_parent_path(path)):
        return

    try:
        send2trash(path)
    except Exception as e:
        log.exception(f"can't trash {path}")
        messagebox.showerror(
            f"Moving to {trash_name} failed",
            f"Moving {path} to {trash_name} failed.\n\n{type(e).__name__}: {e}",
        )
    else:
        messagebox.showinfo(
            f"Moving to {trash_name} succeeded", f"{path.name} was moved to {trash_name}."
        )


def delete(path: Path) -> None:
    if path.is_dir():
        message = f"Do you want to permanently delete {path.name} and everything inside it?"
    else:
        message = f"Do you want to permanently delete {path.name}?"

    if not close_tabs(find_tabs_by_parent_path(path)):
        return
    if not messagebox.askyesno(f"Delete {path.name}", message, icon="warning"):
        return

    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except Exception as e:
        log.exception(f"can't delete {path}")
        messagebox.showerror(
            "Deleting failed", f"Deleting {path} failed:\n\n{type(e).__name__}: {e}"
        )


def rename(old_path: Path) -> None:
    # TODO: checkbox to tell git about the change, checked by default

    new_name = tkinter.simpledialog.askstring('Rename file', f'Enter a new name for {old_path.name}:', initialvalue=old_path.name)
    if new_name is None or new_name == old_path.name:
        return

    # TODO: would be nice to disable ok button instead
    try:
        new_path = old_path.with_name(new_name)  # can raise ValueError("Invalid name '/adf'")
        if new_path.exists():
            raise ValueError(f"There is already a file named {new_name}")
    except ValueError as e:
        # str(e) is e.g. "Invalid name '/adf'"
        messagebox.showerror("Cannot rename", str(e) + ".")
        return

    try:
        old_path.rename(new_path)
    except OSError as e:
        log.exception(f"renaming failed: {old_path} --> {new_path}")
        messagebox.showerror("Renaming failed", str(e) + ".")
        return

    for tab in find_tabs_by_parent_path(old_path):
        tab.path = new_path / tab.path.relative_to(old_path)


def populate_menu(event: tkinter.Event[DirectoryTree]) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)
    project_root = get_path(tree.find_project_id(item))

    if path != project_root:
        tree.contextmenu.add_command(label=f"Move to {trash_name}", command=partial(trash, path))
        tree.contextmenu.add_command(label="Delete", command=partial(delete, path))

    # TODO: does renaming project_root really work? langservers should be restarted etc
    if path.is_dir():
        tree.contextmenu.add_command(label="Rename", command=partial(rename, path))


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", populate_menu, add=True)
