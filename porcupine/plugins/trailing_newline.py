"""Add a trailing newline character to the end of file when saving."""
from __future__ import annotations

import tkinter

from porcupine import get_tab_manager, tabs


def on_save(event: tkinter.Event[tabs.FileTab]) -> None:
    if event.widget.settings.get("insert_final_newline", bool):
        textwidget = event.widget.textwidget
        if textwidget.get("end - 2 chars", "end - 1 char") != "\n":
            # doesn't end with a \n yet, be sure not to annoyingly move the
            # cursor like IDLE does
            cursor = textwidget.index("insert")
            textwidget.insert("end - 1 char", "\n")
            textwidget.mark_set("insert", cursor)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("insert_final_newline", True)
    tab.bind("<<BeforeSave>>", on_save, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
