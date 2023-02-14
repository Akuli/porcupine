from __future__ import annotations

from typing import Callable, Any
from porcupine import get_main_window
from porcupine.menubar import get_filetab
from porcupine import tabs

import tkinter

ftab_indexes = []


def text_is_selected(tab: tabs.FileTab) -> bool:
    try:
        selected_text = tab.textwidget.get("sel.first", "sel.last")
    except tkinter.TclError:
        # nothing selected
        return False
    return True

def init_menu() -> None:
    global rm
    rm = tkinter.Menu(get_main_window(), tearoff=0)

def show_menu(event) -> None:

    if rm.index("end") is not None:
        flag = bool
        try:
            flag=text_is_selected(get_filetab())
        except AssertionError:
            flag=False
        finally:
            if flag:
                for i in ftab_indexes:
                    rm.entryconfigure(ftab_indexes, state=tkinter.NORMAL)
            else:
                for i in ftab_indexes:
                    rm.entryconfigure(ftab_indexes, state=tkinter.DISABLED)
        rm.tk_popup(event.x_root, event.y_root)
        rm.bind("<Unmap>", (lambda event: rm.after_idle(rm.update)), add=True)

def add_rightclick_option(path: str, func: Callable):
    rm.add_command(label=path, command=func)

def add_filetab_command(path: str, func: Callable[[tabs.FileTab], object] | None = None, **kwargs: Any) -> None:
    if func is None:
        command = lambda: get_filetab().event_generate(f"<<FiletabCommand:{path}>>")
    else:
        command = lambda: func(get_filetab())  # type: ignore

    rm.add_command(label=path, command=command, **kwargs)
    ftab_indexes.append(rm.index("end"))


def setup()-> None:
    init_menu()

    w = get_main_window()
    w.bind("<<RightClick>>", show_menu)




