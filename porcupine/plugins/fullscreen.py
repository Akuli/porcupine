"""Full Screen button in the View menu."""
import tkinter

from porcupine import get_main_window, menubar


def setup() -> None:
    var = tkinter.BooleanVar()
    var.trace_add("write", (lambda *junk: get_main_window().attributes("-fullscreen", var.get())))
    menubar.get_menu("View").add_checkbutton(label="Full Screen", variable=var)
