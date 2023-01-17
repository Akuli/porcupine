"""Adds a command-line option "--create-desktop-launcher" to Porcupine.

When you run "porcu --create-desktop-launcher", it creates a double-clickable
launcher to the user's desktop. The launcher runs Porcupine.

Currently --create-desktop-launcher works only on Linux.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from porcupine import images


class CreateLauncherAction(argparse.Action):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["nargs"] = 0
        super().__init__(*args, **kwargs)

    def __call__(self, *args: object) -> None:
        # str() needed to work around mypy bugginess
        if str(sys.platform) == "linux":
            sys.exit("Error: --create-desktop-launcher can only be used on Linux")

        venv = os.environ.get("VIRTUAL_ENV")
        if not venv or not (Path(venv) / "bin" / "porcu").is_file():
            sys.exit(
                "Error: --create-desktop-launcher can only be used when Porcupine is installed into a virtualenv"
            )

        # launcher_path is basically ~/Desktop/Porcupine.desktop.
        # But if your OS is not in english it could be e.g. ~/Työpöytä/Porcupine.desktop.
        output = subprocess.check_output(["xdg-user-dir", "DESKTOP"], text=True)
        launcher_path = Path(output.strip("\n")) / "Porcupine.desktop"

        with launcher_path.open("w") as file:
            file.write("[Desktop Entry]\n")
            file.write("Name=Porcupine\n")
            file.write(f"Exec={venv}/bin/porcu\n")
            file.write("Terminal=false\n")
            file.write("Type=Application\n")
            file.write(f"Icon={images.images_dir}/logo-200x200.gif\n")

        # To make a launcher usable, it must be marked as executable.
        # How to "chmod +x" in python: https://stackoverflow.com/a/12792002
        execute_permissions = 0o111
        launcher_path.chmod(launcher_path.stat().st_mode | execute_permissions)

        print(f"Created {launcher_path}")
        sys.exit(0)


def setup_argument_parser(parser: argparse.ArgumentParser) -> None:
    if sys.platform == "linux":
        parser.add_argument(
            "--create-desktop-launcher",
            action=CreateLauncherAction,
            help="create a double-clickable Porcupine launcher icon to desktop (Linux only)",
        )


def setup() -> None:
    pass
