from __future__ import annotations
import logging
import sys
from functools import partial
from pathlib import Path
from tkinter import messagebox
import shutil

from porcupine import tabs
from porcupine.plugins.directory_tree import DirectoryTree, get_path
from porcupine import utils, get_paned_window, get_tab_manager

from send2trash import send2trash


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
            f"Moving {path} to {trash_name} failed:\n\n{type(e).__name__}: {e}",
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

    if not messagebox.askyesno(f"Delete {path.name}", message, icon="warning"):
        return
    if not close_tabs(find_tabs_by_parent_path(path)):
        return

    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except Exception as e:
        log.exception(f"can't delete {path}")
        messagebox.showerror(
            f"Deleting failed", f"Deleting {path} failed:\n\n{type(e).__name__}: {e}"
        )


def populate_menu(event) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)
    project_root = get_path(tree.find_project_id(item))

    if path != project_root:
        tree.contextmenu.add_command(label=f"Move to {trash_name}", command=partial(trash, path))
        tree.contextmenu.add_command(label="Delete", command=partial(delete, path))


def setup() -> None:
    for widget in utils.get_children_recursively(get_paned_window()):
        if isinstance(widget, DirectoryTree):
            utils.bind_with_data(widget, "<<PopulateContextMenu>>", populate_menu, add=True)
