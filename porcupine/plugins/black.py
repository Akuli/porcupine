# TODO: add other formatters, at least isort
from __future__ import annotations

import logging
import subprocess
import traceback
from functools import partial
from pathlib import Path
from tkinter import messagebox

from porcupine import get_tab_manager, menubar, tabs, textwidget, utils
from porcupine.plugins import python_venv

log = logging.getLogger(__name__)


def run_black(code: str, path: Path | None) -> str:
    python = python_venv.find_python(None if path is None else utils.find_project_root(path))
    if python is None:
        messagebox.showerror(
            "Can't find a Python installation", "You need to install Python to run black."
        )
        return code

    try:
        # run black in subprocess just to make sure that it can't crash porcupine
        # set cwd so that black finds its config in pyproject.toml
        #
        # FIXME: file must not be named black.py or similar
        result = subprocess.run(
            [str(python), "-m", "black", "-"],
            check=True,
            stdout=subprocess.PIPE,
            cwd=(Path.home() if path is None else path.parent),
            input=code.encode("utf-8"),
        )
        return result.stdout.decode("utf-8")
    except Exception:
        log.exception("running black failed")
        messagebox.showerror("Running black failed", traceback.format_exc())
        return code


def black_the_code(tab: tabs.FileTab, event: object) -> None:
    before = tab.textwidget.get("1.0", "end - 1 char")
    after = run_black(before, tab.path)
    if before != after:
        with textwidget.change_batch(tab.textwidget):
            tab.textwidget.replace("1.0", "end - 1 char", after)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.bind("<<FiletabCommand:Tools/Python/Black>>", partial(black_the_code, tab), add=True)


def setup() -> None:
    menubar.add_filetab_command("Tools/Python/Black")
    get_tab_manager().add_filetab_callback(on_new_filetab)
