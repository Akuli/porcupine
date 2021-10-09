"""Reload file from disk automatically."""
from __future__ import annotations

from porcupine import get_tab_manager, tabs


# TODO: should cursor and scrolling stuff be a part of reload()?
def reload_if_necessary(tab: tabs.FileTab) -> None:
    if tab.other_program_changed_file():
        cursor_pos = tab.textwidget.index("insert")
        scroll_fraction = tab.textwidget.yview()[0]
        if tab.reload():
            tab.textwidget.mark_set("insert", cursor_pos)
            tab.textwidget.yview_moveto(scroll_fraction)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.bind("<<FileSystemChanged>>", (lambda e: reload_if_necessary(tab)), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
