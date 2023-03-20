"""
Installs an entry for Porcupine in the desktop menu system.
You can enable it in Porcupine's settings.

This plugin doesn't do anything on Windows or MacOS.
"""

import os
import shlex
import shutil
import subprocess
import tkinter
from pathlib import Path
from tkinter import messagebox, ttk

from porcupine import dirs, images, settings

setup_after = ["filetypes"]  # To group the checkbutton on the bottom

XDG_DESKTOP_MENU = "xdg-desktop-menu"
DESKTOP_FILE_NAME = "Porcupine.desktop"


def install_desktop_file() -> None:
    venv = os.environ.get("VIRTUAL_ENV")
    if not venv or not (Path(venv) / "bin" / "porcu").is_file():
        messagebox.showerror(
            "Creating menu entry failed",
            "Porcupine must be installed in a virtual environment in order to create a desktop menu entry.",
        )
        return

    activate_path = Path(venv) / "bin" / "activate"
    assert activate_path.is_file()

    launcher_path = dirs.user_cache_path / DESKTOP_FILE_NAME

    with launcher_path.open("w") as file:
        file.write("[Desktop Entry]\n")
        file.write("Name=Porcupine\n")
        file.write("GenericName=Text Editor\n")
        # Must activate the venv, otherwise various things don't work
        # (e.g. os.environ.get("VIRTUAL_ENV") in this plugin)
        bash_command = f"source {shlex.quote(str(activate_path))} && porcu"
        file.write(f"Exec=bash -c {shlex.quote(bash_command)}\n")
        file.write("Terminal=false\n")
        file.write("Type=Application\n")
        file.write("Categories=TextEditor;Development;\n")
        file.write(f"Icon={images.images_dir}/logo-200x200.gif\n")

    subprocess.call([XDG_DESKTOP_MENU, "install", "--mode", "user", "--novendor", launcher_path])
    launcher_path.unlink()


def uninstall_desktop_file() -> None:
    subprocess.call([XDG_DESKTOP_MENU, "uninstall", "--mode", "user", DESKTOP_FILE_NAME])


# Can't use settings.add_checkbutton() because it makes a checkbox that
# gets unchecked when you reset all settings. This leaves the user in a
# weird situation where Porcupine is installed but can't be launched
# from the menu.
def add_checkbox_to_settings() -> None:
    checkbutton = ttk.Checkbutton(
        settings.get_dialog_content(), text="Show Porcupine in the desktop menu system"
    )
    checkbutton.grid(column=0, columnspan=2, sticky="w", pady=2)

    desktop_file_exists = (
        (Path("~/.local/share/applications") / DESKTOP_FILE_NAME).expanduser().exists()
    )
    var = tkinter.BooleanVar(value=desktop_file_exists)
    checkbutton.config(variable=var)

    def var_changed(*junk: object) -> None:
        if var.get():
            install_desktop_file()
        else:
            uninstall_desktop_file()

    var.trace_add("write", var_changed)


def setup() -> None:
    if shutil.which(XDG_DESKTOP_MENU):
        add_checkbox_to_settings()
