from __future__ import annotations

from typing import Callable, Any
from porcupine import get_main_window, tabs
from porcupine.menubar import get_filetab

import tkinter

_ftab_indexes_ = []
_menu_items_ = {}


def text_is_selected(tab: tabs.FileTab) -> bool:
    try:
        tab.textwidget.get("sel.first", "sel.last")
    except tkinter.TclError:
        # nothing selected
        return False
    return True


def show_menu(event) -> None:
    rm = tkinter.Menu(get_main_window(), tearoff=0)

    for path, func in _menu_items_.items():
        rm.add_command(label=path, command=func)


    if rm.index("end") is not None:
        flag = bool
        try:
            flag=text_is_selected(get_filetab())
        except AssertionError:
            flag=False
        finally:
            if flag:
                for i in _ftab_indexes_:
                    rm.entryconfigure(i, state=tkinter.NORMAL)
            else:
                for i in _ftab_indexes_:
                    rm.entryconfigure(i, state=tkinter.DISABLED)
        rm.tk_popup(event.x_root, event.y_root)
        rm.bind("<Unmap>", (lambda event: rm.after_idle(rm.update)), add=True)

def add_rightclick_option(path: str, func):
    _menu_items_[path] = func
def add_filetab_command(path: str, func: Callable[[tabs.FileTab], object] | None = None, **kwargs: Any) -> None:
    if func is None:
        command = lambda: get_filetab().event_generate(f"<<FiletabCommand:{path}>>")
    else:
        command = lambda: func(get_filetab())  # type: ignore

    _menu_items_[path] = command
    _ftab_indexes_.append(len(_menu_items_) - 1)


def setup()-> None:

    w = get_main_window()
    w.bind("<<RightClick>>", show_menu)




