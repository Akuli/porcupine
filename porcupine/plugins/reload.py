"""Reload file from disk automatically."""
from functools import partial

from porcupine import get_tab_manager, tabs


def reload_if_necessary(tab: tabs.FileTab, junk: object) -> None:
    if tab.other_program_changed_file():
        cursor_pos = tab.textwidget.index("insert")
        scroll_fraction = tab.textwidget.yview()[0]  # type: ignore[no-untyped-call]
        if tab.reload():
            tab.textwidget.mark_set("insert", cursor_pos)
            tab.textwidget.yview_moveto(scroll_fraction)  # type: ignore[no-untyped-call]


def on_new_filetab(tab: tabs.FileTab) -> None:
    callback = partial(reload_if_necessary, tab)
    tab.bind("<<TabSelected>>", callback, add=True)
    tab.textwidget.bind("<FocusIn>", callback, add=True)
    tab.textwidget.bind("<Button-1>", callback, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
