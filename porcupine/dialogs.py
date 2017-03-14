"""Simple wrapper module around tkinter.filedialog.

Functions in this module always set the initial directory to where the
user was last time.
"""

import os
from tkinter import filedialog


_default_options = {
    'filetypes': [("Python files", "*.py"), ("All files", "*")],
    'initialdir': os.getcwd(),
}


def open_file(**kwargs):
    options = _default_options.copy()
    options["title"] = "Open file"
    options.update(kwargs)

    path = filedialog.askopenfilename(**options)
    if not path:
        # the user cancelled, the path is ''
        return None

    path = os.path.abspath(path)
    _default_options['initialdir'] = os.path.dirname(path)
    return path


def save_as(**kwargs):
    options = _default_options.copy()
    options["title"] = "Save as"
    options.update(kwargs)

    path = filedialog.asksaveasfilename(**options)
    if not path:
        return None

    path = os.path.abspath(path)
    _default_options['initialdir'] = os.path.dirname(path)
    return path
