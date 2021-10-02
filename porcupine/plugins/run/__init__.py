"""Compile, run and lint files."""
from __future__ import annotations
from tkinter import messagebox
from porcupine import menubar, tabs

from . import no_terminal, terminal, dialog


def ask_and_run_command(tab: tabs.FileTab) -> None:
    if tab.path is None:
        # TODO: this isn't great, maybe just make substitutions not available?
        messagebox.showerror(
            "File not saved", "You need to save the file before you can run commands."
        )
        return

    command_info = dialog.ask_command(tab.path)
    if command_info is not None:
        command, cwd, external_terminal = command_info
        if external_terminal:
            terminal.run_command(command, cwd)
        else:
            no_terminal.run_command(command, cwd)


def setup() -> None:
    menubar.add_filetab_command("Run/Run command", ask_and_run_command)
