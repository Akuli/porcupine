"""Simple fullscreen mode button."""

import tkinter as tk

from porcupine import utils


def on_var_changed(variable_name, junk, trace_mode):
    root = utils.get_root()
    root.attributes('-fullscreen', root.getvar(variable_name))


def setup(editor):
    var = tk.BooleanVar()
    var.trace('w', on_var_changed)

    def toggle_var():
        var.set(not var.get())

    # add_action only supports command items, but that's why the menus
    # are also exposed :)
    editor.add_action(toggle_var, binding='<F11>')
    menu = editor.get_menu("View")
    menu.add_checkbutton(label="Full Screen", accelerator='F11',
                         variable=var)
