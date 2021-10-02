"""Compile, run and lint files."""
from __future__ import annotations

from tkinter import messagebox

from porcupine import menubar, tabs

from . import dialog, history, no_terminal, terminal


def ask_and_run_command(tab: tabs.FileTab) -> None:
    if tab.path is None:
        # TODO: this isn't great, maybe just make substitutions not available?
        messagebox.showerror(
            "File not saved", "You need to save the file before you can run commands."
        )
        return

    # FIXME: python_venv plugin integration
    info = dialog.ask_command(tab.path)
    if info is not None:
        history.add(info)
        if info.external_terminal:
            terminal.run_command(info.command, info.cwd)
        else:
            no_terminal.run_command(info.command, info.cwd)


def setup() -> None:
    history.setup()
    menubar.add_filetab_command("Run/Run command", ask_and_run_command)
