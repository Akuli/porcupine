"""
This module doesn't do much. It just displays dialogs and tries to guess
what would be a good default directory and/or file.
"""

import functools
import os
from tkinter import filedialog

import porcupine


last_options = {}


def _dialog(action, last_path):
    # pygments supports so many different kinds of file types that
    # showing them all would be insane
    # TODO: allow configuring which file types are shown
    options = {'filetypes': [("All files", "*")]}

    # the mro thing is there to avoid import cycles (lol)
    tab = porcupine.get_tab_manager().current_tab
    if any(cls.__name__ == 'FileTab' for cls in type(tab).__mro__):
        if tab.filetype.patterns:
            options['filetypes'].insert(
                0, ("%s files" % tab.filetype.name, tab.filetype.patterns))
        elif 'filetypes' in last_options:
            options['filetypes'] = last_options['filetypes']

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
