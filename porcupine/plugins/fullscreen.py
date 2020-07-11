from functools import partial
import tkinter

from porcupine import actions, get_main_window


def on_var_changed(var: tkinter.Variable, *junk: str) -> None:
    window = get_main_window()
    window.attributes('-fullscreen', var.get())


def setup() -> None:
    action = actions.add_yesno("View/Full Screen", False, '<F11>')
    action.var.trace_add('write', partial(on_var_changed, action.var))
