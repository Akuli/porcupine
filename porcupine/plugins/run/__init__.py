"""Compile, run and lint files."""
from __future__ import annotations

from tkinter import messagebox
from typing import Any, List

from porcupine import get_tab_manager, menubar, settings, tabs

from . import dialog, history, no_terminal, terminal


def ask_and_run_command(tab: tabs.FileTab) -> None:
    if tab.path is None:
        # TODO: this isn't great, maybe just make substitutions not available?
        messagebox.showerror(
            "File not saved", "You need to save the file before you can run commands."
        )
        return

    # FIXME: python_venv plugin integration goes everywhere
    info = dialog.ask_command(tab)
    if info is not None:
        history.add(info)
        if info.external_terminal:
            terminal.run_command(info.command, info.cwd)
        else:
            no_terminal.run_command(info.command, info.cwd)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("example_commands", [], type_=List[history.ExampleCommand])


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    settings.add_option("run_history", [], type_=List[Any])
    menubar.add_filetab_command("Run/Run command", ask_and_run_command)
