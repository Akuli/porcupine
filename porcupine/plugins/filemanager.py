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


ask_file_name_text = {
    "rename": ("Rename", "Enter a new name for {name}:"),
    "new": ("New file", "Enter a name for the new file:"),
    "paste": ("File conflict", "There is already a file named {name} in {parent}\n\n"),
}


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


def show_error(title: str, message: str, error: Exception) -> None:
    log.exception(message)
    messagebox.showerror(title, message, detail=f"{type(error).__name__}: {error}")


def ask_file_name(target_dir: Path, old_name: str, mode: str, can_overwrite: bool = False) -> Path | None:
    dialog = tkinter.Toplevel()
    dialog.transient(get_main_window())

    big_frame = ttk.Frame(dialog, padding=10)
    big_frame.pack(fill="both", expand=True)

    for i in {0, 1}:
        big_frame.columnconfigure(i, weight=1)

    phrase_label = ttk.Label(big_frame, wraplength=400)
    phrase_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="ew")

    file_name_var = tkinter.StringVar(value=old_name)
    overwrite_var = tkinter.BooleanVar(value=False)

    entry = ttk.Entry(big_frame, textvariable=file_name_var)
    entry.grid(row=3, column=0, columnspan=2, sticky="ew")

    new_path = None

    def select_name() -> None:
        nonlocal new_path
        if overwrite_var.get():
            new_path = target_dir / old_name
        else:
            new_path = (target_dir / "dummy").with_name(entry.get())
        dialog.destroy()

    cancel_button = ttk.Button(big_frame, text="Cancel", command=dialog.destroy, width=1)
    cancel_button.grid(row=4, column=0, padx=(0, 5), pady=(20, 0), sticky="ew")

    ok_button = ttk.Button(big_frame, text="OK", command=select_name, state="disabled", width=1)
    ok_button.grid(row=4, column=1, padx=(5, 0), pady=(20, 0), sticky="ew")

    if can_overwrite:
        r1 = ttk.Radiobutton(big_frame, text="Overwrite", variable=overwrite_var, value=True)
        r2 = ttk.Radiobutton(
            big_frame, text="Change name of destination", variable=overwrite_var, value=False
        )
        r1.grid(row=1, column=0, columnspan=2, sticky="ew")
        r2.grid(row=2, column=0, columnspan=2, pady=(5, 20), sticky="ew")

        r1.invoke()
        ok_button.config(state="normal")
        entry.config(state="disabled")

    assert mode in ask_file_name_text
    dialog_title, dialog_phrase = ask_file_name_text[mode]

    if mode == "paste":
        if can_overwrite:
            dialog_phrase += "What do you want to do with it?"
        else:
            dialog_phrase += "Choose a name that isn't in use."

    phrase_label.config(text=dialog_phrase.format(name=old_name, parent=target_dir))

    def update_dialog_state(*junk: object) -> None:
        if overwrite_var.get():
            ok_button.config(state="normal")
            entry.config(state="disabled")
            return

        entry.config(state="normal")
        name = entry.get()
        try:
            possible_new_path = (target_dir / "dummy").with_name(name)
        except ValueError:
            ok_button.config(state="disabled")
            return

        ok_button["state"] = "disabled" if possible_new_path.exists() else "normal"

    file_name_var.trace_add("write", update_dialog_state)
    overwrite_var.trace_add("write", update_dialog_state)
    entry.bind("<Return>", (lambda event: ok_button.invoke()), add=True)
    entry.bind("<Escape>", (lambda event: cancel_button.invoke()), add=True)
    entry.select_range(0, "end")
    entry.focus()

    dialog.title(dialog_title)
    dialog.resizable(False, False)
    dialog.wait_window()

    return new_path


# Not necessarily same concept as Porcupine's project root
def find_git_root(path: Path) -> Path | None:
    for parent in path.parents:
        if (parent / ".git").is_dir():
            return parent
    return None


def move_with_git_or_otherwise(old_path: Path, new_path: Path) -> bool:
    old_git = find_git_root(old_path)
    new_git = find_git_root(new_path)
    if old_git is not None and new_git is not None and old_git == new_git:
        log.info(f"attemting 'git mv' ({old_path} --> {new_path})")
        try:
            subprocess.check_call(
                ["git", "mv", "--", str(old_path), str(new_path)],
                cwd=old_path.parent,
                **utils.subprocess_kwargs,
            )
            return True
        except (OSError, subprocess.CalledProcessError):
            # Happens when:
            #   - git not installed
            #   - old_path is not 'git add'ed
            pass

    log.info(f"moving without git ({old_path} --> {new_path})")
    try:
        shutil.move(str(old_path), str(new_path))
    except OSError as e:
        show_error("Moving failed", f"Cannot move {old_path} to {new_path}.", e)
        return False

    for tab in find_tabs_by_parent_path(old_path):
        assert tab.path is not None
        tab.path = new_path / tab.path.relative_to(old_path)
    return True


def rename(old_path: Path) -> None:
    new_path = ask_file_name(old_path.parent, old_path.name, mode="rename")
    if new_path is not None:
        if move_with_git_or_otherwise(old_path, new_path):
            get_tab_manager().event_generate("<<FileSystemChanged>>")
            get_directory_tree().select_file(new_path)


def paste(new_path: Path) -> None:
    global paste_state
    assert paste_state is not None

    if not new_path.is_dir():
        new_path = new_path.parent

    new_file_path = new_path / paste_state.path.name

    if new_file_path.exists():
        path = ask_file_name(
            new_file_path.parent,
            new_file_path.name,
            mode="paste",
            can_overwrite=paste_state.path.parent != new_file_path.parent,
        )
        if path is None:
            return
        new_file_path = path

    if paste_state.is_cut:
        if not move_with_git_or_otherwise(paste_state.path, new_file_path):
            return
        paste_state = None
    else:
        try:
            shutil.copy(paste_state.path, new_file_path)
        except OSError as e:
            show_error("Copying failed", f"Cannot copy {paste_state.path} to {new_file_path}.", e)
            return

    get_tab_manager().event_generate("<<FileSystemChanged>>")
    get_directory_tree().select_file(new_file_path)


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
    except Exception as e:  # can be send2trash's own error, idk if maybe OSError
        show_error(f"Can't move to {trash_name}", f"Moving {path} to {trash_name} failed.", e)
        return

    get_tab_manager().event_generate("<<FileSystemChanged>>")


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
        show_error("Deleting failed", f"Deleting {path} failed.", e)
        return

    get_tab_manager().event_generate("<<FileSystemChanged>>")


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
    callback: Callable[[Path], None | str]

    def run(self, event: tkinter.Event[DirectoryTree]) -> None:
        path = get_selected_path(event.widget)
        if path is not None and self.condition(path):
            self.callback(path)


def is_NOT_project_root(path: Path) -> bool:
    return path not in map(get_path, get_directory_tree().get_children())


def can_paste(path: Path) -> bool:
    return paste_state is not None and paste_state.path.is_file()


def new_file_here(path: Path) -> str:
    name = ask_file_name(path, "", mode="new")
    if name:
        name.touch()
        get_tab_manager().open_file(name)
    return "break"  # must do, otherwise others will handle Ctrl+N


commands = [
    # Doing something to an entire project is more difficult than you would think.
    # For example, if the project is renamed, venv locations don't update.
    # TODO: update venv locations when the venv is renamed
    Command("New file", "<<FileManager:New file>>", (lambda p: p.is_dir()), new_file_here),
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
