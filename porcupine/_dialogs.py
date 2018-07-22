"""
This module doesn't do much. It just displays dialogs and tries to guess
what would be a good default directory and/or file.
"""

import functools
import mimetypes
import os
from tkinter import filedialog

import porcupine.filetypes


last_options = {}


def _dialog(action, last_path):
    options = {}

    # this is generated here because opening a file of a type supported
    # by Pygments creates a new filetype object (see filetypes.py)
    options['filetypes'] = [("All files", "*")]
    for filetype in porcupine.filetypes.get_all_filetypes():
        patterns = list(filetype.filename_patterns)
        if filetype.name not in {'Plain Text', 'Porcupine filetypes.ini'}:
            for mimetype in filetype.mimetypes:
                patterns.extend(mimetypes.guess_all_extensions(mimetype))

        # TODO: does passing a tuple of patterns work?
        #       the tkinter user inside me says that it will work because Tcl
        #       arrays are just space-separated strings
        options['filetypes'].append((filetype.name, ' '.join(patterns)))

    # the mro thing is there to avoid import cycles (lol)
    tab = porcupine.get_tab_manager().select()
    if any(cls.__name__ == 'FileTab' for cls in type(tab).__mro__):
        if tab.path is not None:
            options['initialdir'] = os.path.dirname(tab.path)
        elif 'initialdir' in last_options:
            options['initialdir'] = last_options['initialdir']

    last_options.clear()
    last_options.update(options)

    if action == 'open':
        assert last_path is None
        options['title'] = "Open Files"

        filenames = [os.path.abspath(file)
                     for file in filedialog.askopenfilenames(**options)]
        if filenames:
            last_options['initialdir'] = os.path.dirname(filenames[0])
        return filenames

    assert action == 'save'
    options['title'] = "Save As"
    if last_path is not None:
        options['initialdir'] = os.path.dirname(last_path)
        options['initialfile'] = os.path.basename(last_path)

    # filename can be '' if the user cancelled
    filename = filedialog.asksaveasfilename(**options)
    if filename:
        filename = os.path.abspath(filename)
        last_options['defaultdir'] = os.path.dirname(filename)
        return filename
    return None


open_files = functools.partial(_dialog, 'open', None)
save_as = functools.partial(_dialog, 'save')
