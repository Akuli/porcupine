"""
Installs an entry for Porcupine in the desktop menu system.
You can enable it in Porcupine's settings.
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
DESKTOP_FILE_PATH = Path(dirs.user_config_dir) / "Porcupine.desktop"


def create_desktop_file(venv_path: Path) -> None:
    activate_path = venv_path / "bin" / "activate"
    assert activate_path.is_file()

    with DESKTOP_FILE_PATH.open("w") as file:
        file.write("[Desktop Entry]\n")
        file.write("Name=Porcupine\n")
        file.write("GenericName=Text Editor\n")
        # Must activate the venv, otherwise various things don't work
        # (e.g. os.environ.get("VIRTUAL_ENV") in this plugin)
        bash_command = f"source {shlex.quote(str(activate_path))} && porcu"
        file.write(f"Exec=bash -c {bash_command}\n")
        file.write("Terminal=false\n")
        file.write("Type=Application\n")
        file.write("Categories=TextEditor;Development;\n")
        file.write(f"Icon={images.images_dir}/logo-200x200.gif\n")


def install_desktop_file() -> None:
    venv = os.environ.get("VIRTUAL_ENV")
    if not venv or not (Path(venv) / "bin" / "porcu").is_file():
        messagebox.showerror(
            "Creating menu entry failed",
            "Porcupine must be installed in a virtual environment in order to create a desktop menu entry.",
        )
        return

    create_desktop_file(Path(venv))
    subprocess.call(
        [XDG_DESKTOP_MENU, "install", "--mode", "user", "--novendor", DESKTOP_FILE_PATH]
    )


def uninstall_desktop_file() -> None:
    subprocess.call([XDG_DESKTOP_MENU, "uninstall", "--mode", "user", "Porcupine.desktop"])
    DESKTOP_FILE_PATH.unlink()


# Can't use settings.add_checkbutton() because it makes a checkbox that
# gets unchecked when you reset all settings. This leaves the user in a
# weird situation where Porcupine is installed but can't be launched
# from the menu.
def add_checkbox_to_settings() -> None:
    checkbutton = ttk.Checkbutton(
        settings.get_dialog_content(), text="Show Porcupine in the desktop menu system"
    )
    checkbutton.grid(column=0, columnspan=2, sticky="w", pady=2)

    var = tkinter.BooleanVar(value=DESKTOP_FILE_PATH.exists())
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
