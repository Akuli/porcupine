from __future__ import annotations

import tkinter
from typing import Callable, Dict, List

from porcupine import get_main_window, get_tab_manager, tabs
from porcupine.menubar import get_filetab

_ftab_indexes: list[int] = []
_menu_items: dict[str, Callable[[], object]] = {}


def text_is_selected(tab: tabs.FileTab) -> bool:
    try:
        tab.textwidget.get("sel.first", "sel.last")
    except tkinter.TclError:
        # nothing selected
        return False
    return True


# creating and showing menu are separated for tests
def create_menu() -> tkinter.Menu:
    rm = tkinter.Menu(get_main_window(), tearoff=0)

    for path, func in _menu_items.items():
        rm.add_command(label=path, command=func)

    flag = text_is_selected(get_filetab())
    if not flag:
        for i in _ftab_indexes:
            rm.entryconfigure(i, state=tkinter.DISABLED)

    return rm


def show_menu(event: tkinter.Event[tkinter.Misc]) -> None:
    rm = create_menu()
    rm.tk_popup(event.x_root + 10, event.y_root + 10)
    rm.bind("<Unmap>", (lambda event: rm.after_idle(rm.destroy)), add=True)


def add_rightclick_option(
    path: str, func: Callable[[tabs.FileTab], object], *, needs_selected_text: bool = False
) -> None:
    assert path not in _menu_items
    _menu_items[path] = lambda: func(get_filetab())
    if needs_selected_text:
        _ftab_indexes.append(len(_menu_items) - 1)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.textwidget.bind("<<RightClick>>", show_menu, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
