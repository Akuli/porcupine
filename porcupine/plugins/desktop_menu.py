"""
Installs an entry for Porcupine in the desktop menu system.
You can enable it in Porcupine's settings.
"""

import os
import shutil
import subprocess
from pathlib import Path
from tkinter import messagebox

from porcupine import dirs, get_tab_manager, images, settings
from porcupine.settings import global_settings

setup_after = ["filetypes"]  # To group the checkbutton on the bottom

XDG_DESKTOP_MENU = "xdg-desktop-menu"


def create_desktop_file(venv_path: str) -> Path:
    file_path = Path(dirs.user_cache_dir) / "Porcupine.desktop"

    with file_path.open("w") as file:
        file.write("[Desktop Entry]\n")
        file.write("Name=Porcupine\n")
        file.write("GenericName=Text Editor\n")
        file.write(f"Exec={venv_path}/bin/porcu\n")
        file.write("Terminal=false\n")
        file.write("Type=Application\n")
        file.write("Categories=TextEditor;Development;\n")
        file.write(f"Icon={images.images_dir}/logo-200x200.gif\n")

    return file_path


def install_uninstall_desktop_file(junk_event: object) -> None:
    if global_settings.get("has_desktop_file", bool):
        venv = os.environ.get("VIRTUAL_ENV")
        if not venv or not (Path(venv) / "bin" / "porcu").is_file():
            messagebox.showerror(
                "Creating menu entry failed",
                "Porcupine must be installed in a virtual environment in order to create a desktop menu entry.",
            )
            global_settings.set("has_desktop_file", False)
            return None

        launcher_path = create_desktop_file(venv)
        subprocess.call(
            [XDG_DESKTOP_MENU, "install", "--mode", "user", "--novendor", launcher_path]
        )
    else:
        subprocess.call([XDG_DESKTOP_MENU, "uninstall", "--mode", "user", "Porcupine.desktop"])


def setup() -> None:
    if not shutil.which("xdg-desktop-menu"):
        return

    global_settings.add_option("has_desktop_file", False)
    settings.add_checkbutton("has_desktop_file", text="Show Porcupine in the desktop menu system")
    get_tab_manager().bind(
        "<<GlobalSettingChanged:has_desktop_file>>", install_uninstall_desktop_file, add=True
    )
