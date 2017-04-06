import contextlib
import hashlib
import logging
import os
import shutil
import tkinter as tk
from tkinter import messagebox
import traceback

from porcupine import dialogs, find, plugins, tabs, textwidget
from porcupine.settings import config

log = logging.getLogger(__name__)


@contextlib.contextmanager
def _backup_open(path, *args, **kwargs):
    """Like open(), but use a backup file if needed."""
    if os.path.exists(path):
        # there's something to back up
        name, ext = os.path.splitext(path)
        while os.path.exists(name + ext):
            name += '-backup'
        backuppath = name + ext

        log.info("backing up '%s' to '%s'", path, backuppath)
        shutil.copy(path, backuppath)

        try:
            yield open(path, *args, **kwargs)
        except Exception as e:
            # oops, let's restore from our backup
            log.info("restoring '%s' from the backup", path)
            shutil.move(backuppath, path)
            raise e
        else:
            log.info("deleting '%s'" % backuppath)
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
    >>> _shorten_filepath('really_really_long_file_name.py', '/')
    '...ly_really_long_file_name.py'
    """
    if len(name) <= 30:
        return name

    try:
        # try to break it by sep in last 27 characters because
        # 27 + len('...') == 30
        # index returns the start of search string so name[where2cut:]
        # will start with sep
        where2cut = name.index(sep, -27)
    except ValueError:
        # no sep in name[-27:], just truncate it
        where2cut = -27
    return '...' + name[where2cut:]


class FileTab(tabs.Tab):
    """A tab in the editor.

    This class implements all tab specific things using other classes.
    """

    def __init__(self, manager):
        super().__init__(manager)
        self._path = None
        self.on_path_changed = []   # callbacks that are called with no args

        self._orig_label_fg = self.label['fg']
        self.on_path_changed.append(self._update_top_label)

        self.mainframe = tk.Frame(self.content)
        self.mainframe.pack(fill='both', expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.MainText(
            self.mainframe, width=1, height=1, wrap='none')
        self.textwidget.on_modified.append(self._update_top_label)
        self.scrollbar = tk.Scrollbar(self.mainframe)

        self.textwidget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar['command'] = self.textwidget.yview

        # these are packed right-to-left because the linenumbers are at
        # left and can be pack_forgot()ten
        self.scrollbar.pack(side='right', fill='y')
        self.textwidget.pack(side='right', fill='both', expand=True)

        self._findwidget = None

        self.mark_saved()
        self._update_top_label()

        self._plugin_state = plugins.init_filetab(self)

    def _get_hash(self):
        result = hashlib.md5()
        encoding = config['files:encoding']  # superstitious speed-up
        for chunk in self.textwidget.iter_chunks():
            chunk = chunk.encode(encoding, errors='replace')
            result.update(chunk)
        return result.hexdigest()

    def mark_saved(self):
        """Make the tab look like it's saved."""
        self._save_hash = self._get_hash()
        self._update_top_label()

    def is_saved(self):
        """Return False if the text has changed since previous save.

        Use mark_saved() to set this.
        """
        return self._get_hash() == self._save_hash

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, new_name):
        # TODO: use os.path.samefile() or something else that takes in
        # account things like case-insensitive paths?
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

        if self.is_saved():
            self.label['fg'] = self._orig_label_fg
        else:
            self.label['fg'] = 'red'

    def can_be_closed(self):
        """If needed, display a 'wanna save?' dialog and save.

        Return False if the user cancels and True otherwise.
        """
        if not self.is_saved():
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

    def close(self):
        super().close()
        plugins.destroy_filetab(self._plugin_state)

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
                for chunk in self.textwidget.iter_chunks():
                    f.write(chunk)
        except (OSError, UnicodeError):
            log.exception("saving '%s' failed", self.path)
            messagebox.showerror("Saving failed!", traceback.format_exc())
            return

        self.mark_saved()

    def save_as(self):
        path = dialogs.save_as(old_path=self.path)
        if path is not None:
            self.path = path
            self.save()

    def find(self):
        if self._findwidget is None:
            log.debug("find widget not created yet, creating it")
            self._findwidget = find.Finder(self.content, self.textwidget)
        self._findwidget.pack(fill='x')


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
