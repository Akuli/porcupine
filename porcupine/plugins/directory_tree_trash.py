import logging
import sys
from functools import partial
from pathlib import Path
from tkinter import messagebox

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


def trash(path: Path) -> None:
    for tab in get_tab_manager().tabs():
        if isinstance(tab, tabs.FileTab) and tab.path is not None and (path == tab.path or path in tab.path.parents):
            if not tab.can_be_closed():
                return
            get_tab_manager().close_tab(tab)

    try:
        send2trash(path)
    except Exception as e:
        log.exception(f"can't trash {path}")
        messagebox.showerror("Trashing failed", f"Moving {path} to {trash_name} failed:\n\n{type(e).__name__}: {e}")
    else:
        messagebox.showinfo("Trashing succeeded", f"{path.name} was moved to {trash_name}.")


def populate_menu(event) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)
    project_root = get_path(tree.find_project_id(item))
    if path == project_root:
        return

    # FIXME: close everything first
    tree.contextmenu.add_command(label=f"Move to {trash_name}", command=partial(trash, path))


def setup() -> None:
    for widget in utils.get_children_recursively(get_paned_window()):
        if isinstance(widget, DirectoryTree):
            utils.bind_with_data(widget, "<<PopulateContextMenu>>", populate_menu, add=True)
