"""
Format the imports of the current file with isort.

Available in Tools/Python/Isort.
"""

from __future__ import annotations

import logging
import subprocess
import traceback
from pathlib import Path
from tkinter import messagebox

from porcupine import menubar, tabs, textutils, utils
from porcupine.plugins import python_venv

log = logging.getLogger(__name__)


def run_isort(code: str, path: Path | None) -> str:
    python = python_venv.find_python(None if path is None else utils.find_project_root(path))
    if python is None:
        messagebox.showerror(
            "Can't find a Python installation", "You need to install Python to run isort."
        )
        return code

    try:
        # run isort in subprocess just to make sure that it can't crash porcupine
        # set cwd so that isort finds its config in pyproject.toml
        #
        # FIXME: file must not be named isort.py or similar
        result = subprocess.run(
            [str(python), "-m", "isort", "-"],
            check=True,
            stdout=subprocess.PIPE,
            cwd=(Path.home() if path is None else path.parent),
            input=code.encode("utf-8"),
        )
        return result.stdout.decode("utf-8")
    except Exception:
        log.exception("running isort failed")
        messagebox.showerror("Running isort failed", traceback.format_exc())
        return code


def isorten_the_code(tab: tabs.FileTab) -> None:
    before = tab.textwidget.get("1.0", "end - 1 char")
    after = run_isort(before, tab.path)
    if before != after:
        with textutils.change_batch(tab.textwidget):
            tab.textwidget.replace("1.0", "end - 1 char", after)


def setup() -> None:
    menubar.add_filetab_command("Tools/Python/Isort", isorten_the_code)
