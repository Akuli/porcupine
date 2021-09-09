"""File manager operations (delete, rename etc) when right-clicking directory tree."""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tkinter
from functools import partial
from pathlib import Path
from tkinter import messagebox, ttk

from send2trash import send2trash

from porcupine import get_main_window, get_tab_manager, tabs, utils
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
    except OSError as e:
        log.exception(f"can't delete {path}")
        messagebox.showerror(
            "Deleting failed", f"Deleting {path} failed:\n\n{type(e).__name__}: {e}"
        )


def _ask_name_for_renaming(old_path: Path) -> Path | None:
    label_width = 400

    dialog = tkinter.Toplevel()
    dialog.transient(get_main_window())
    dialog.resizable(False, False)
    dialog.title("Rename")

    big_frame = ttk.Frame(dialog)
    big_frame.pack(fill="both", expand=True)
    ttk.Label(
        big_frame, text=f"Enter a new name for {old_path.name}:", wraplength=label_width
    ).pack(fill="x", padx=10, pady=10)

    var = tkinter.StringVar()
    entry = ttk.Entry(big_frame, textvariable=var)
    entry.pack(pady=40)
    entry.insert(0, old_path.name)

    button_frame = ttk.Frame(big_frame)
    button_frame.pack(fill="x", pady=10)

    new_path = None

    def select_name() -> None:
        nonlocal new_path
        new_path = old_path.with_name(entry.get())
        dialog.destroy()

    cancel_button = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
    cancel_button.pack(side="left", expand=True)
    ok_button = ttk.Button(button_frame, text="OK", command=select_name, state="disabled")
    ok_button.pack(side="right", expand=True)

    def validate_name(*junk: object) -> None:
        name = entry.get()
        try:
            possible_new_path = old_path.with_name(name)
        except ValueError:
            ok_button.config(state="disabled")
            return

        if possible_new_path.exists():
            ok_button.config(state="disabled")
        else:
            ok_button.config(state="normal")

    var.trace_add("write", validate_name)
    entry.bind("<Return>", (lambda event: ok_button.invoke()), add=True)
    entry.bind("<Escape>", (lambda event: cancel_button.invoke()), add=True)
    entry.select_range(0, "end")
    entry.focus()

    dialog.wait_window()
    return new_path


def rename(old_path: Path) -> None:
    new_path = _ask_name_for_renaming(old_path)
    if new_path is None:
        return

    try:
        subprocess.check_call(
            ["git", "mv", "--", old_path.name, new_path.name],
            cwd=old_path.parent,
            **utils.subprocess_kwargs,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        # Happens when:
        #   - git not installed
        #   - project doesn't use git
        #   - old_path is not 'git add'ed
        log.info("'git mv' failed, moving without git", exc_info=True)
        try:
            old_path.rename(new_path)
        except OSError:
            log.exception(f"renaming failed: {old_path} --> {new_path}")
            messagebox.showerror("Renaming failed", str(e))
            return

    for tab in find_tabs_by_parent_path(old_path):
        assert tab.path is not None
        tab.path = new_path / tab.path.relative_to(old_path)


def open_in_file_manager(path: Path) -> None:
    windowingsystem = get_main_window().tk.call("tk", "windowingsystem")

    # Using Popen to make sure it won't freeze gui
    # No freezing without it on windows and linux, but just to be sure
    if windowingsystem == "win32":
        # Refactoring note: explorer.exe exits with status 1 on success (lol)
        subprocess.Popen(["explorer.exe", str(path)])
    elif windowingsystem == "x11":
        subprocess.Popen(["xdg-open", str(path)])
    else:
        # not tested :(
        subprocess.Popen(["open", str(path)])


def populate_menu(event: tkinter.Event[DirectoryTree]) -> None:
    tree: DirectoryTree = event.widget
    [item] = tree.selection()
    path = get_path(item)
    project_root = get_path(tree.find_project_id(item))

    # Doing something to an entire project is more difficult than you would think.
    # For example, if the project is renamed, venv locations don't update.
    # TODO: update venv locations when the venv is renamed
    if path != project_root:
        tree.contextmenu.add_command(label="Rename", command=partial(rename, path))
        tree.contextmenu.add_command(label=f"Move to {trash_name}", command=partial(trash, path))
        tree.contextmenu.add_command(label="Delete", command=partial(delete, path))

    if path.is_dir():
        tree.contextmenu.add_command(
            label="Open in file manager", command=partial(open_in_file_manager, path)
        )


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", populate_menu, add=True)
