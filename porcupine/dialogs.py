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


def open_files(**kwargs):
    options = _default_options.copy()
    options["title"] = "Open file"
    options.update(kwargs)

    paths = filedialog.askopenfilenames(**options)
    if not paths:
        # paths is actually '', not [] or ()
        return []

    result = [os.path.abspath(path) for path in paths]
    _default_options['initialdir'] = os.path.dirname(result[-1])
    return result


def save_as(*, old_path=None, **kwargs):
    options = _default_options.copy()
    if old_path is not None:
        options['initialdir'], options['initialfile'] = os.path.split(old_path)
    options["title"] = "Save as"
    options.update(kwargs)

    path = filedialog.asksaveasfilename(**options)
    if not path:
        return None

    path = os.path.abspath(path)
    _default_options['initialdir'] = os.path.dirname(path)
    return path
