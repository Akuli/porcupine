import tkinter

from porcupine import actions, get_main_window


def on_var_changed(variable_name, junk, trace_mode):
    window = get_main_window()
    window.attributes('-fullscreen', window.getvar(variable_name))


def setup():
    action = actions.add_yesno("View/Full Screen", False, '<F11>')
    action.var.trace('w', on_var_changed)
