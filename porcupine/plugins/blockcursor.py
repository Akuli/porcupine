"""Toggles between the ❚ and | cursor state of the textwidgets."""
from __future__ import annotations

import tkinter

from porcupine import get_tab_manager, settings, tabs


def do_toggle(event: tkinter.Event[tkinter.Misc]) -> None:
    if settings.get("blockcursor", object):
        event.widget.config(blockcursor=True, insertwidth=0)  # minimize the cursor thickness
    else:
        event.widget.config(blockcursor=False, insertwidth=2)  # set insertwidth back to tk default


def on_new_filetab(tab: tabs.FileTab) -> None:
    is_block = settings.get("blockcursor", object)
    tab.textwidget.config(blockcursor=is_block, insertwidth=0 if is_block else 2)
    tab.textwidget.bind("<<SettingChanged:blockcursor>>", do_toggle, add=True)


def setup() -> None:
    settings.add_option("blockcursor", False)
    settings.add_checkbutton("blockcursor", text="Use blockcursor")
    get_tab_manager().add_filetab_callback(on_new_filetab)

