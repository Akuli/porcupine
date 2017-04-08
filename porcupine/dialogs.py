"""Native file dialog functions.

Tkinter uses native file dialogs provided by the OS on Mac OSX and
Windows, but the X11 dialog looks stupid and breaks with dark Porcupine
themes. This module uses a GTK+ dialog instead on X11 if possible.
"""

import os
from tkinter import filedialog

from porcupine import utils

# the gtk stuff in this module is mostly based on this:
# https://python-gtk-3-tutorial.readthedocs.io/en/latest/dialogs.html
try:
    from gi.repository import Gtk, GLib
except ImportError:
    Gtk = None
    GLib = None


_filetypes = [
    # (name, glob, mimetype)
    ("Python files", '*.py', 'text/x-python'),
    ("All files", '*', None),
]


def _gtk_dialog(action, title, default):
    if action == 'open':
        dialog = Gtk.FileChooserDialog(
            title, None, Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK),
            select_multiple=True,
        )
        if default is not None:
            dialog.set_current_folder(default)

    if action == 'save':
        dialog = Gtk.FileChooserDialog(
            title, None, Gtk.FileChooserAction.SAVE,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_SAVE, Gtk.ResponseType.OK),
            do_overwrite_confirmation=True,
        )
        if default is not None:
            dialog.set_filename(default)

    for name, glob, mimetype in _filetypes:
        filefilter = Gtk.FileFilter()
        filefilter.set_name(name)   # can't use an initialization argument :(
        filefilter.add_pattern(glob)
        filefilter.the_pattern = glob   # gtk wants to hide this from me
        if mimetype is not None:
            filefilter.add_mime_type(mimetype)
        dialog.add_filter(filefilter)

    response = dialog.run()
    if response == Gtk.ResponseType.OK:
        if action == 'open':
            result = dialog.get_filenames()
        if action == 'save':
            result = dialog.get_filename()

            # this overwrites silently if 'hello' doesn't exist,
            # 'hello.py' exists and the user wants to save as 'hello',
            # but i can't find a better way to do this
            glob = dialog.get_filter().the_pattern
            if glob.startswith('*.'):    # e.g. '*.py'
                extension = glob[1:]     # e.g. '.py'
                if not result.endswith(extension):
                    result += extension
    else:
        if action == 'open':
            result = []
        if action == 'save':
            result = None

    dialog.destroy()

    # run Gtk's mainloop until the dialog has disappeared
    context = GLib.MainLoop().get_context()
    while context.iteration(False):
        pass

    return result


def _tkinter_dialog(action, title, default):
    options = {
        'filetypes': [(name, glob) for name, glob, mimetype in _filetypes],
        'title': title,
    }

    if action == 'open':
        if default is not None:
            options['initialdir'] = default
        filenames = filedialog.askopenfilenames(**options)
        return [os.path.abspath(filename) for filename in filenames]

    if action == 'save':
        if default is not None:
            options['initialfile'] = default
        filename = filedialog.asksaveasfilename(**options)

        # the filename might be '' if the user cancels, so can't compare
        # with None
        if filename:
            return os.path.abspath(filename)
        return None


def _dialog(*args):
    if Gtk is None:
        func = _tkinter_dialog
    elif utils.get_root().tk.call('tk', 'windowingsystem') != 'x11':
        func = _tkinter_dialog
    else:
        func = _gtk_dialog
    return func(*args)


def open_files(defaultdir=None):
    return _dialog('open', "Open files", defaultdir)


def save_as(old_path=None):
    return _dialog('save', "Save as", old_path)
