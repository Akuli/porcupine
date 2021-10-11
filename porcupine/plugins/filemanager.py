"""File manager operations (delete, rename etc) when right-clicking directory tree."""
from __future__ import annotations

import dataclasses
import logging
import shutil
import subprocess
import sys
import tkinter
from functools import partial
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, NamedTuple

from send2trash import send2trash

from porcupine import get_main_window, get_tab_manager, tabs, utils
from porcupine.plugins.directory_tree import DirectoryTree, get_directory_tree, get_path

setup_after = ["directory_tree"]
log = logging.getLogger(__name__)

if sys.platform == "win32":
    trash_name = "recycle bin"
else:
    trash_name = "trash"


class PasteState(NamedTuple):
    is_cut: bool
    path: Path


paste_state: PasteState | None = None


def find_tabs_by_parent_path(path: Path) -> list[tabs.FileTab]:
    return [
        tab
        for tab in get_tab_manager().tabs()
        if isinstance(tab, tabs.FileTab)
        and tab.path is not None
        and (path == tab.path or path in tab.path.parents)
    ]


def ask_file_name(
    old_path: Path, is_paste: bool = False, show_overwriting_option: bool = False
) -> Path | None:
    label_width = 400

    dialog = tkinter.Toplevel()
    dialog.transient(get_main_window())
    dialog.resizable(False, False)

    big_frame = ttk.Frame(dialog, padding=10)
    big_frame.pack(fill="both", expand=True)

    dialog_title = "Rename"
    dialog_phrase = f"Enter a new name for {old_path.name}:"

    if is_paste:
        dialog_title = "File conflict"
        if show_overwriting_option:
            dialog_phrase = (
                f"{old_path.parent} already has a file named {old_path.name}.\nDo you want to"
                " overwrite it?"
            )
        else:
            dialog_phrase = (
                f"{old_path.parent} already has a file named {old_path.name}.\nChoose a name that"
                " isn't in use."
            )

    dialog.title(dialog_title)
    ttk.Label(big_frame, text=dialog_phrase, wraplength=label_width).pack(fill="x")

    entry_frame = ttk.Frame(big_frame)
    entry_frame.pack(fill="x")
    file_name_var = tkinter.StringVar()
    entry = ttk.Entry(entry_frame, textvariable=file_name_var)
    entry.pack(pady=40, side=tkinter.BOTTOM, fill="x")
    entry.insert(0, old_path.name)

    button_frame = ttk.Frame(big_frame)
    button_frame.pack(fill="x", pady=(10, 0))

    new_path = None
    overwrite_var = tkinter.BooleanVar(value=False)

    def select_name() -> None:
        nonlocal new_path
        if overwrite_var.get():
            new_path = old_path
        else:
            new_path = old_path.with_name(entry.get())
        dialog.destroy()

    cancel_button = ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=1)
    cancel_button.pack(side="left", expand=True, fill="x", padx=(0, 5))
    ok_button = ttk.Button(button_frame, text="OK", command=select_name, state="disabled", width=1)
    ok_button.pack(side="right", expand=True, fill="x", padx=(5, 0))

    if is_paste and show_overwriting_option:
        r1 = ttk.Radiobutton(entry_frame, text="Overwrite", variable=overwrite_var, value=True)
        r2 = ttk.Radiobutton(
            entry_frame, text="Change name of destination", variable=overwrite_var, value=False
        )
        r1.pack(pady=(40, 0), fill="x")
        r1.invoke()
        r2.pack(fill="x")
        ok_button.config(state="normal")
        entry.config(state="disabled")

    def update_dialog_state(*junk: object) -> None:
        if overwrite_var.get():
            ok_button.config(state="normal")
            entry.config(state="disabled")
            return

        entry.config(state="normal")
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

    overwrite_var.trace_add("write", update_dialog_state)
    file_name_var.trace_add("write", update_dialog_state)
    entry.bind("<Return>", (lambda event: ok_button.invoke()), add=True)
    entry.bind("<Escape>", (lambda event: cancel_button.invoke()), add=True)
    entry.select_range(0, "end")
    entry.focus()

    dialog.wait_window()

    return new_path


def rename(old_path: Path) -> None:
    new_path = ask_file_name(old_path)
    if new_path is None:
        return

    try:
        subprocess.check_call(
            ["git", "mv", "--", old_path.name, new_path.name],
            cwd=old_path.parent,
            **utils.subprocess_kwargs,
        )
    except (OSError, subprocess.CalledProcessError):
        # Happens when:
        #   - git not installed
        #   - project doesn't use git
        #   - old_path is not 'git add'ed
        log.info("'git mv' failed, moving without git", exc_info=True)
        try:
            old_path.rename(new_path)
        except OSError as e:
            log.exception(f"renaming failed: {old_path} --> {new_path}")
            messagebox.showerror("Renaming failed", str(e))
            return

    for tab in find_tabs_by_parent_path(old_path):
        assert tab.path is not None
        tab.path = new_path / tab.path.relative_to(old_path)


def paste(new_path: Path) -> None:
    global paste_state
    assert paste_state is not None

    if not new_path.is_dir():
        new_path = new_path.parent

    new_file_path = new_path / paste_state.path.name

    if new_file_path.exists():
        path = ask_file_name(
            new_file_path,
            is_paste=True,
            show_overwriting_option=(paste_state.path.parent != new_file_path.parent),
        )
        if path is None:
            return
        new_file_path = path

        if paste_state.path == new_file_path:  # user pressed X or cancel on conflict dialog
            return

    if paste_state.is_cut:
        shutil.move(str(paste_state.path), str(new_file_path))
        for tab in find_tabs_by_parent_path(paste_state.path):
            assert tab.path is not None
            tab.path = new_file_path
        paste_state = None
    else:
        shutil.copy(paste_state.path, new_file_path)

    get_directory_tree().refresh()


def copy(old_path: Path) -> None:
    global paste_state
    paste_state = PasteState(False, old_path)


def cut(old_path: Path) -> None:
    global paste_state
    paste_state = PasteState(True, old_path)


def close_tabs(tabs_to_close: list[tabs.FileTab]) -> bool:
    if not all(tab.can_be_closed() for tab in tabs_to_close):
        return False

    for tab in tabs_to_close:
        get_tab_manager().close_tab(tab)
    return True


def trash(path: Path) -> None:
    if path.is_dir():
        message = f"Do you want to move {path.name} and everything inside it to {trash_name}?"
    else:
        message = f"Do you want to move {path.name} to {trash_name}?"

    if not messagebox.askyesno(f"Move {path.name} to {trash_name}", message, icon="warning"):
        return
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
    except OSError as e:
        log.exception(f"can't delete {path}")
        messagebox.showerror(
            "Deleting failed", f"Deleting {path} failed.\n\n{type(e).__name__}: {e}"
        )


def open_in_file_manager(path: Path) -> None:
    windowingsystem = get_main_window().tk.call("tk", "windowingsystem")
    if windowingsystem == "win32":
        # Refactoring note: explorer.exe exits with status 1 on success (lol)
        opener_command = "explorer.exe"
    elif windowingsystem == "x11":
        opener_command = "xdg-open"
    else:
        opener_command = "open"

    # Using Popen to make sure it won't freeze gui
    # No freezing without it on windows and linux, but just to be sure
    # DO NOT add **utils.subprocess_kwargs, otherwise does nothing on windows
    subprocess.Popen([opener_command, str(path)])


def get_selected_path(tree: DirectoryTree) -> Path | None:
    try:
        [item] = tree.selection()
    except ValueError:
        # nothing selected
        return None
    return get_path(item)


@dataclasses.dataclass
class Command:
    name: str
    virtual_event_name: str | None
    condition: Callable[[Path], bool]
    callback: Callable[[Path], None]

    def run(self, event: tkinter.Event[DirectoryTree]) -> None:
        path = get_selected_path(event.widget)
        if path is not None and self.condition(path):
            self.callback(path)


def is_NOT_project_root(path: Path) -> bool:
    return path not in map(get_path, get_directory_tree().get_children())


def can_paste(path: Path) -> bool:
    return paste_state is not None and paste_state.path.is_file()


commands = [
    # Doing something to an entire project is more difficult than you would think.
    # For example, if the project is renamed, venv locations don't update.
    # TODO: update venv locations when the venv is renamed
    Command("Cut", "<<Cut>>", (lambda p: not p.is_dir()), cut),
    Command("Copy", "<<Copy>>", (lambda p: not p.is_dir()), copy),
    Command("Paste", "<<Paste>>", can_paste, paste),
    Command("Rename", "<<FileManager:Rename>>", is_NOT_project_root, rename),
    Command(f"Move to {trash_name}", "<<FileManager:Trash>>", is_NOT_project_root, trash),
    Command("Delete", "<<FileManager:Delete>>", is_NOT_project_root, delete),
    Command("Open in file manager", None, (lambda p: p.is_dir()), open_in_file_manager),
]


def populate_menu(event: tkinter.Event[DirectoryTree]) -> None:
    tree = event.widget
    path = get_selected_path(tree)
    if path is not None:
        for command in commands:
            if command.condition(path):
                tree.contextmenu.add_command(
                    label=command.name, command=partial(command.callback, path)
                )


def setup() -> None:
    tree = get_directory_tree()
    tree.bind("<<PopulateContextMenu>>", populate_menu, add=True)

    for command in commands:
        if command.virtual_event_name is not None:
            tree.bind(command.virtual_event_name, command.run, add=True)
