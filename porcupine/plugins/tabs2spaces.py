"""If configuration says so, insert spaces when the tab key is pressed."""
# This plugin binds Tab and Shift-Tab, and always returns 'break'.
# If you are writing a plugin that binds Tab or Shift-Tab too, it
# **must** be set up before this plugin. For example:
#
#    setup_before = ['tabs2spaces']
#
# As a side note, if your plugin binds <Shift-Tab> it should
# probably use porcupine.utils.bind_tab_key instead.
from __future__ import annotations

import tkinter

from porcupine import get_tab_manager, tabs, textwidget, utils


def on_tab_key(event: tkinter.Event[textwidget.MainText], shift_pressed: bool) -> utils.BreakOrNone:
    if not event.widget.tag_ranges("sel"):
        # nothing selected
        if shift_pressed:
            event.widget.dedent("insert")
        else:
            event.widget.indent("insert")

    # don't insert a tab when it's not supposed to be inserted, or if
    # shift is pressed down, don't move focus out of the widget
    return "break"


def on_new_filetab(tab: tabs.FileTab) -> None:
    utils.bind_tab_key(tab.textwidget, on_tab_key, add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_filetab)
