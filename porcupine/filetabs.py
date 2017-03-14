import contextlib
import hashlib
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import traceback

from . import config, highlight, linenumbers, scrolling, tabs, textwidget


@contextlib.contextmanager
def backup_open(path, *args, **kwargs):
    """Like open(), but use a backup file if needed."""
    if os.path.exists(path):
        # there's something to back up
        name, ext = os.path.splitext(path)
        while os.path.exists(name + ext):
            name += '-backup'
        backuppath = name + ext

        shutil.copy(path, backuppath)
        try:
            yield open(path, *args, **kwargs)
        except Exception as e:
            # oops, let's restore from our backup
            shutil.move(backuppath, path)
            raise e
        else:
            # it worked, let's clean up
            os.remove(backuppath)

    else:
        yield open(path, *args, **kwargs)


# The sep argument is just for doctesting.
def shorten_filepath(name, sep=os.sep):
    """Create a representation of a path at most 30 characters long.

    >>> shorten_filepath('/tmp/test.py', '/')
    '/tmp/test.py'
    >>> shorten_filepath('/home/someusername/path/to/test.py', '/')
    '.../path/to/test.py'
    """
    if len(name) <= 30:
        return name

    try:
        # try to break it by sep in last 27 characters because
        # 27 + len('...') == 30
        # index returns the start of search string so name[where2cut:]
        # will start with sep
        where2cut = name.index(sep, -27)
    except IndexError:
        # no sep in name[-27:], just truncate it
        where2cut = -27
    return '...' + name[where2cut:]


class FileTab(tabs.Tab):
    """A tab in the editor."""

    def __init__(self):
        super().__init__()
        self._path = None
        self.on_path_changed = []   # callbacks that are called with no args
        self.textwidget = None      # just for _get_hash
        self.mark_saved()

    def _get_hash(self):
        if self.textwidget is None:
            # nothing here yet
            content = b''
        else:
            encoding = config['files']['encoding']
            content = self.textwidget.get('1.0', 'end-1c')
            content = content.encode(encoding, errors='replace')

        return hashlib.md5(content).hexdigest()

    def mark_saved(self):
        """Make the tab look like it's saved."""
        self._save_hash = self._get_hash()
        if self.label is not None:
            # the widgets have been created
            self._update_label()

    @property
    def saved(self):
        """True if the text looks like has been saved.

        Use mark_saved() to set this.
        """
        return self._get_hash() == self._save_hash

    def create_widgets(self, tabmanager):
        super().create_widgets(tabmanager)

        self._orig_label_fg = self.label['fg']
        self.on_path_changed.append(self._update_label)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.EditorText(
            self.content, width=1, height=1)
        self.textwidget.on_modified.append(self._update_label)
        self._update_label()

        if config['gui'].getboolean('linenumbers'):
            linenums = linenumbers.LineNumbers(self.content, self.textwidget)
            self.textwidget.on_modified.append(linenums.do_update)
            scrollbar = scrolling.MultiScrollbar(
                self.content, [self.textwidget, linenums])
        else:
            linenums = None
            scrollbar = scrolling.MultiScrollbar(
                self.content, [self.textwidget])

        highlighter = highlight.Highlighter(self.textwidget)
        self.textwidget.on_modified.append(highlighter.highlight)

        if config['gui'].getboolean('statusbar'):
            self.statusbar = tk.Label(self.content, anchor='w',
                                      relief='sunken')
            self.statusbar.pack(fill='x')
            self.textwidget.on_cursor_move.append(self._update_statusbar)
            self._update_statusbar()
        else:
            self.statusbar = None

        # The statusbar is the bottommost widget, but it must be packed
        # first to get it below everything else. That's why nothing was
        # packed until now.
        if self.statusbar is not None:
            self.statusbar.pack(side='bottom', fill='x')
        if linenums is not None:
            linenums.pack(side='left', fill='y')
        self.textwidget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='left', fill='y')

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, new_name):
        assert self.label is not None, \
            "cannot set name before creating widgets"
        it_changes = (self._path != new_name)
        self._path = new_name
        if it_changes:
            for callback in self.on_path_changed:
                callback()

    def _update_label(self):
        if self.path is None:
            self.label['text'] = "New file"
        else:
            self.label['text'] = shorten_filepath(self.path)

        if self.saved:
            self.label['fg'] = self._orig_label_fg
        else:
            self.label['fg'] = 'red'

    def _update_statusbar(self):
        line, column = self.textwidget.index('insert').split('.')
        self.statusbar['text'] = "Line %s, column %s" % (line, column)

    def can_be_closed(self):
        """If needed, display a 'wanna save?' dialog and save.

        Return False if the user cancels and True otherwise.
        """
        if not self.saved:
            if self.path is None:
                msg = "Do you want to save your changes?"
            else:
                msg = ("Do you want to save your changes to %s?"
                       % self.path)
            answer = messagebox.askyesnocancel("Close file", msg)
            if answer is None:
                # cancel
                return False
            if answer:
                # yes
                self.save()
        return True

    def focus(self):
        self.textwidget.focus()

    def get_dialog_options(self):
        result = {'filetypes': [("Python files", "*.py"), ("All files", "*")]}
        if self.path is None:
            result['initialdir'] = os.getcwd()
        else:
            result['initialdir'] = os.path.dirname(self.path)
            result['initialfile'] = os.path.basename(self.path)
        return result

    def save(self):
        if self.path is None:
            self.save_as()
            return

        if self.textwidget.get('end-2c', 'end-1c') != '\n':
            # doesn't end with a \n yet
            if config['files'].getboolean('add_trailing_newline'):
                # make sure we don't move the cursor, IDLE does it and
                # it's annoying
                here = self.textwidget.index('insert')
                self.textwidget.insert('end-1c', '\n')
                self.textwidget.mark_set('insert', here)

        try:
            encoding = config['files']['encoding']
            with backup_open(self.path, 'w', encoding=encoding) as f:
                f.write(self.textwidget.get('1.0', 'end-1c'))
        except (OSError, UnicodeError):
            messagebox.showerror("Saving failed!", traceback.format_exc())
            return

        self.mark_saved()

    def save_as(self):
        options = self.get_dialog_options()
        path = filedialog.asksaveasfilename(**options)
        if path:
            # not cancelled
            self.path = path
            self.save()


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
