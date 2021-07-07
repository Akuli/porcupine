"""Toggles between the ❚ and | cursor state when the insert key is pressed."""
from __future__ import annotations

import tkinter

from porcupine import get_tab_manager, tabs, settings


def on_insert_key(event: tkinter.Event) -> str:
    event.widget["blockcursor"] = False if event.widget["blockcursor"] else True
    settings.set_("blockcursor", bool(event.widget["blockcursor"]))
    return "break"  # sometimes the insert key also inserts the content of the cb, we abort it


def on_filetab(tab: tabs.FileTab) -> None:
    tab.textwidget.config(blockcursor=settings.get("blockcursor", object))
    tab.textwidget.bind("<Insert>", on_insert_key, add=True)
    tab.textwidget.bind("<KP_Insert>", on_insert_key, add=True)


def setup() -> None:
    settings.add_option("blockcursor", False)
    get_tab_manager().add_filetab_callback(on_filetab)

