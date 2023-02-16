from __future__ import annotations

import tkinter

from porcupine import get_main_window, tabs
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


    flag = bool
    try:
        flag=text_is_selected(get_filetab())
    except AssertionError:
        flag=False
    finally:
        if not flag:
            for i in _ftab_indexes:
                rm.entryconfigure(i, state=tkinter.DISABLED)

    rm.tk_popup(event.x_root, event.y_root)
    rm.bind("<Unmap>", (lambda event: rm.after_idle(rm.destroy)), add=True)

def add_rightclick_option(path: str, func, needs_selected_text: bool = False):
    if not needs_selected_text:
        _menu_items[path] = func
    else:
        if func is None:
            command = lambda: get_filetab().event_generate(f"<<FiletabCommand:{path}>>")
        else:
            command = lambda: func(get_filetab())  # type: ignore

        _menu_items[path] = command
        _ftab_indexes.append(len(_menu_items) - 1)



def setup()-> None:

    w = get_main_window()
    w.bind("<<RightClick>>", show_menu)




