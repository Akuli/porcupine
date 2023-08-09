"""
Format the current file with black or isort.

Available in Tools/Python/Black and Tools/Python/Isort.
"""

from __future__ import annotations

import logging
import subprocess
import traceback
from functools import partial
from pathlib import Path
from tkinter import messagebox

from porcupine import actions, menubar, tabs, textutils, utils
from porcupine.plugins import python_venv

log = logging.getLogger(__name__)


def run_tool(tool: str, code: str, path: Path | None) -> str:
    python = python_venv.find_python(None if path is None else utils.find_project_root(path))
    if python is None:
        messagebox.showerror(
            "Can't find a Python installation", f"You need to install Python to run {tool}."
        )
        return code

    fail_str = f"Running {tool} failed"

    try:
        # run in subprocess just to make sure that it can't crash porcupine
        # set cwd so that black/isort finds its config in pyproject.toml
        #
        # FIXME: file must not be named black.py or similar
        result = subprocess.run(
            [str(python), "-m", tool, "-"],
            check=True,
            capture_output=True,
            cwd=(Path.home() if path is None else path.parent),
            input=code.encode("utf-8"),
        )
        return result.stdout.decode("utf-8")
    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            fail_str,
            utils.tkinter_safe_string(e.stderr.decode("utf-8"), hide_unsupported_chars=True),
        )
    except Exception:
        log.exception(f"running {tool} failed")
        messagebox.showerror(fail_str, traceback.format_exc())

    return code


def format_code_in_textwidget(tool: str, tab: tabs.FileTab) -> None:
    before = tab.textwidget.get("1.0", "end - 1 char")
    after = run_tool(tool, before, tab.path)
    if before != after:
        with textutils.change_batch(tab.textwidget):
            tab.textwidget.replace("1.0", "end - 1 char", after)


def setup() -> None:
    black_format_tab_action = actions.register_filetab_action(
        name="Black Format Tab",
        description="Autoformat open tab using Black",
        callback=partial(format_code_in_textwidget, "black"),
        availability_callback=actions.filetype_is("Python"),
    )

    isort_format_tab_action = actions.register_filetab_action(
        name="isort Format Tab",
        description="Sort Imports of open tab with isort",
        callback=partial(format_code_in_textwidget, "isort"),
        availability_callback=actions.filetype_is("Python"),
    )

    menubar.add_filetab_action("Tools/Python", black_format_tab_action)
    menubar.add_filetab_action("Tools/Python", isort_format_tab_action)
