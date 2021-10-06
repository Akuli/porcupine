"""Compile, run and lint files."""
from __future__ import annotations

import sys
from pathlib import Path
from tkinter import messagebox
from typing import Any, List

from porcupine import get_tab_manager, menubar, settings, tabs, utils
from porcupine.plugins import python_venv

from . import dialog, history, no_terminal, terminal


def run(command: history.Command, project_root: Path) -> None:
    history.add(command)

    venv = python_venv.get_venv(project_root)
    if venv is None:
        command_string = command.command
    else:
        if sys.platform == "win32":
            activate = utils.quote(str(venv / "Scripts" / "activate"))
            # https://stackoverflow.com/a/8055390
            command_string = f"{activate} & {command.command}"
        else:
            activate = utils.quote(str(venv / "bin" / "activate"))
            command_string = f". {activate}\n{command.command}"

    if command.external_terminal:
        terminal.run_command(command_string, Path(command.cwd))
    else:
        no_terminal.run_command(command_string, Path(command.cwd))


def ask_and_run_command(tab: tabs.FileTab) -> None:
    if not tab.save():
        return
    assert tab.path is not None

    project_root = utils.find_project_root(tab.path)
    info = dialog.ask_command(tab, project_root)
    if info is not None:
        run(info, project_root)


def repeat_command(tab: tabs.FileTab) -> None:
    if not tab.save():
        return
    assert tab.path is not None

    project_root = utils.find_project_root(tab.path)
    previous_commands = history.get(tab, project_root)
    if previous_commands:
        run(previous_commands[0], project_root)
    else:
        choose = utils.get_binding("<<Menubar:Run/Run command>>")
        repeat = utils.get_binding("<<Menubar:Run/Repeat previous command>>")
        messagebox.showerror(
            "No commands to repeat",
            f"Please press {choose} to choose a command to run. You can then repeat it with"
            f" {repeat}.",
        )


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("example_commands", [], type_=List[history.ExampleCommand])


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    settings.add_option("run_history", [], type_=List[Any])
    menubar.add_filetab_command("Run/Run command", ask_and_run_command)
    menubar.add_filetab_command("Run/Repeat previous command", repeat_command)
