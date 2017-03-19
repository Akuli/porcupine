import contextlib
import hashlib
import os
import shutil
import tkinter as tk
from tkinter import messagebox
import traceback

from porcupine import (autocomplete, dialogs, highlight, linenumbers,
                       scrolling, tabs, textwidget)
from porcupine.settings import config


@contextlib.contextmanager
def _backup_open(path, *args, **kwargs):
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
def _shorten_filepath(name, sep=os.sep):
    """Create a representation of a path at most 30 characters long.

    >>> _shorten_filepath('/tmp/test.py', '/')
    '/tmp/test.py'
    >>> _shorten_filepath('/home/someusername/path/to/test.py', '/')
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

    def __init__(self, manager):
        super().__init__(manager)
        self._path = None
        self.on_path_changed = []   # callbacks that are called with no args

        self._orig_label_fg = self.label['fg']
        self.on_path_changed.append(self._update_top_label)

        mainframe = tk.Frame(self.content)
        mainframe.pack(fill='both', expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.EditorText(
            mainframe, width=1, height=1)
        self.textwidget.on_modified.append(self._update_top_label)
        self.linenumbers = linenumbers.LineNumbers(
            mainframe, self.textwidget, height=1)
        self.textwidget.on_modified.append(self.linenumbers.do_update)

        scrollbar = scrolling.MultiScrollbar(
            mainframe, [self.textwidget, self.linenumbers])

        # these are packed right-to-left because the linenumbers are at
        # left and sometimes pack_forgot()ten
        scrollbar.pack(side='right', fill='y')
        self.textwidget.pack(side='right', fill='both', expand=True)

        self._completer = autocomplete.AutoCompleter(self.textwidget)
        self._completing = False

        self.highlighter = highlight.Highlighter(self.textwidget)
        self.textwidget.on_modified.append(self.highlighter.highlight)

        self.statusbar = tk.Label(self.content, anchor='w',
                                  relief='sunken')
        self.textwidget.on_cursor_move.append(self._update_statusbar)
        self._update_statusbar()

        for key in ['gui:linenumbers', 'gui:statusbar', 
                    'editing:autocomplete', 'editing:font']:
            config.connect(key, self._on_config_changed)
            self._on_config_changed(key, config[key])

        self.mark_saved()
        self._update_top_label()

    def _on_config_changed(self, key, value):
        if key == 'gui:linenumbers':
            if value:
                self.linenumbers.pack(side='left', fill='y')
            else:
                self.linenumbers.pack_forget()

        elif key == 'editing:font':
            self.textwidget['font'] = value
            if self.linenumbers is not None:
                self.linenumbers['font'] = value

        elif key == 'gui:statusbar':
            if value:
                self.statusbar.pack(fill='x')
            else:
                self.statusbar.pack_forget()

        elif key == 'editing:autocomplete':
            if value == self._completing:
                # must not enable or disable completions twice
                return

            # less typing and pep-8 line length
            completer = self._completer
            text = self.textwidget

            if value:
                text.on_complete_previous.append(completer.complete_previous)
                text.on_complete_next.append(completer.complete_next)
                text.on_cursor_move.append(completer.reset)
            else:
                text.on_complete_previous.remove(completer.complete_previous)
                text.on_complete_next.remove(completer.complete_next)
                text.on_cursor_move.remove(completer.reset)

            self._completing = value

    def _get_hash(self):
        content = self.textwidget.get('1.0', 'end-1c')
        content = content.encode(config['files:encoding'], errors='replace')
        return hashlib.md5(content).hexdigest()

    def mark_saved(self):
        """Make the tab look like it's saved."""
        self._save_hash = self._get_hash()
        if self.label is not None:
            # the widgets have been created
            self._update_top_label()

    @property
    def saved(self):
        """True if the text looks like has been saved.

        Use mark_saved() to set this.
        """
        return self._get_hash() == self._save_hash

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

    def _update_top_label(self):
        if self.path is None:
            self.label['text'] = "New file"
        else:
            self.label['text'] = _shorten_filepath(self.path)

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

    def on_focus(self):
        self.textwidget.focus()

    def save(self):
        if self.path is None:
            self.save_as()
            return

        if self.textwidget.get('end-2c', 'end-1c') != '\n':
            # doesn't end with a \n yet
            if config['files:add_trailing_newline']:
                # make sure we don't move the cursor, IDLE does it and
                # it's annoying
                here = self.textwidget.index('insert')
                self.textwidget.insert('end-1c', '\n')
                self.textwidget.mark_set('insert', here)

        try:
            encoding = config['files:encoding']
            with _backup_open(self.path, 'w', encoding=encoding) as f:
                f.write(self.textwidget.get('1.0', 'end-1c'))
        except (OSError, UnicodeError):
            messagebox.showerror("Saving failed!", traceback.format_exc())
            return

        self.mark_saved()

    def save_as(self):
        path = dialogs.save_as(old_path=self.path)
        if path is not None:
            self.path = path
            self.save()


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
