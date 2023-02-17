from __future__ import annotations

import tkinter
from typing import Callable

from porcupine import get_main_window, get_tab_manager, tabs
from porcupine.menubar import get_filetab

_ftab_indexes = []
_menu_items = {}


def text_is_selected(tab: tabs.FileTab) -> bool:
    try:
        tab.textwidget.get("sel.first", "sel.last")
    except tkinter.TclError:
        # nothing selected
        return False
    return True


def show_menu(event) -> None:
    rm = tkinter.Menu(get_main_window(), tearoff=0)

    for path, func in _menu_items.items():
        rm.add_command(label=path, command=func)

    flag = text_is_selected(get_filetab())
    if not flag:
        for i in _ftab_indexes:
            rm.entryconfigure(i, state=tkinter.DISABLED)

    rm.tk_popup(event.x_root, event.y_root)
    rm.bind("<Unmap>", (lambda event: rm.after_idle(rm.destroy)), add=True)


def add_rightclick_option(path: str, func: Callable[[tabs.FileTab], object], needs_selected_text: bool = False) -> None:

    if needs_selected_text:
        _menu_items[path] = lambda: func(get_filetab())
        _ftab_indexes.append(len(_menu_items) - 1)
    else:
        _menu_items[path] = func


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.textwidget.bind("<<RightClick>>", show_menu, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
