"""Compile, run and lint files."""
from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Any, List

from porcupine import get_tab_manager, menubar, settings, tabs, utils

from . import dialog, history, no_terminal, terminal


def run(command: history.Command) -> None:
    history.add(command)
    # FIXME: python_venv plugin integration goes everywhere
    if command["external_terminal"]:
        terminal.run_command(command["command"], Path(command["cwd"]))
    else:
        no_terminal.run_command(command["command"], Path(command["cwd"]))


def ask_and_run_command(tab: tabs.FileTab) -> None:
    if not tab.save():
        return
    assert tab.path is not None

    info = dialog.ask_command(tab, utils.find_project_root(tab.path))
    if info is not None:
        run(info)


def repeat_command(tab: tabs.FileTab) -> None:
    if not tab.save():
        return
    assert tab.path is not None

    previous_commands = history.get(tab, utils.find_project_root(tab.path))
    if previous_commands:
        run(previous_commands[0]["command"])
    else:
        messagebox.showerror(
            "No commands to repeat",
            f"Please press {utils.get_binding('<<Run/Run command>>')} to choose a command to run."
            f" You can then repeat it with {utils.get_binding('<<Run/Repeat previous command>>')}.",
        )


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("example_commands", [], type_=List[history.ExampleCommand])


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    settings.add_option("run_history", [], type_=List[Any])
    menubar.add_filetab_command("Run/Run command", ask_and_run_command)
    menubar.add_filetab_command("Run/Repeat previous command", repeat_command)
