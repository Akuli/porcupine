"""Adds a setting to show the cursor as a block instead of a thin line."""
from __future__ import annotations

from porcupine import get_tab_manager, settings, tabs
from porcupine.settings import global_settings

setup_after = ["filetypes"]  # don't setup it in filename order, so checkbuttons will grouped


def do_toggle(tab: tabs.FileTab) -> None:
    if global_settings.get("blockcursor", bool):
        tab.textwidget.configure(blockcursor=True, insertwidth=0)  # minimize the cursor thickness
    else:
        tab.textwidget.configure(
            blockcursor=False, insertwidth=2
        )  # set insertwidth back to tk default


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.bind("<<GlobalSettingChanged:blockcursor>>", lambda event: do_toggle(tab), add=True)
    do_toggle(tab)


def setup() -> None:
    global_settings.add_option("blockcursor", False)
    settings.add_checkbutton("blockcursor", text="Show cursor as a block instead of a thin line")
    get_tab_manager().add_filetab_callback(on_new_filetab)
