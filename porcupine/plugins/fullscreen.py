import tkinter

import porcupine.menubar


def on_var_changed(variable_name, junk, trace_mode):
    window = porcupine.get_main_window()
    window.attributes('-fullscreen', window.getvar(variable_name))


def setup():
    var = tkinter.BooleanVar()
    var.trace('w', on_var_changed)

    def toggle_var(junk):
        var.set(not var.get())

    # add_action only supports command items, but that's why these
    # things are also exposed :)
    porcupine.get_main_window().bind('<F11>', toggle_var)
    porcupine.menubar.get_menu("View").add_checkbutton(
        label="Full Screen", accelerator='F11', variable=var)
