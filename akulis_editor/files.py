import contextlib
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import traceback

from . import highlight, linenumbers, scrolling, textwidget


@contextlib.contextmanager
def _backup_open(path, *args, **kwargs):
    """Like _open(), but use a backup file if needed."""
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


class File:
    r"""This class represents a new or opened file.

    Currently the editor creates only one File instance, but this class
    will be used to implement tabs (as in browser tabs, not \t
    characters) later.
    """

    def __init__(self, parentwidget, settings):
        self._name = None
        self._settings = settings
        self.on_name_changed = []   # these will be ran like callback(self)

        self.label = tk.Label(parentwidget)
        self._orig_label_fg = self.label['fg']
        self.label.pack()
        self.on_name_changed.append(self._update_label)

        self.content = tk.Frame(parentwidget)
        self.content.pack(fill='both', expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.EditorText(
            self.content, settings, width=1, height=1)
        self.textwidget.bind('<<Modified>>', self._update_label)
        settings['init_textwidget'](self.textwidget)

        if settings['linenumbers']:
            linenums = linenumbers.LineNumbers(
                self.content, self.textwidget, font=settings['font'])
            self.textwidget.on_linecount_changed.append(linenums.do_update)
            scrollbar = scrolling.MultiScrollbar(
                self.content, [self.textwidget, linenums])
        else:
            linenums = None
            scrollbar = scrolling.MultiScrollbar(
                self.content, [self.textwidget])

        highlighter = highlight.SyntaxHighlighter(self.textwidget)
        scrollbar.on_visibility_changed.append(highlighter.do_lines)
        self.textwidget.on_cursor_move.append(
            lambda line, col: highlighter.do_line(line))

        if settings['statusbar']:
            self.statusbar = tk.Label(self.content, anchor='w',
                                      relief='sunken')
            self.statusbar.pack(fill='x')
            self.textwidget.on_cursor_move.append(self._update_statusbar)
            self._update_statusbar(1, 0)
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
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        it_changes = (self._name != new_name)
        self._name = new_name
        if it_changes:
            for callback in self.on_name_changed:
                callback()

    def _update_label(self, event=None):
        if self.name is None:
            self.label['text'] = "New file"
        else:
            # This doesn't use %r to avoid \\ on Windows.
            self.label['text'] = "File '%s'" % self.name

        if self.textwidget.edit_modified():
            self.label['fg'] = 'red'
        else:
            self.label['fg'] = self._orig_label_fg

    def _update_statusbar(self, lineno, column):
        self.statusbar['text'] = "Line %d, column %d" % (lineno, column)

    def savecheck(self, dialogtitle):
        """If needed, display a 'wanna save?' dialog and save.

        Return False if the user cancels and True otherwise.
        """
        if self.textwidget.edit_modified():
            if self.name is None:
                msg = "Do you want to save your changes?"
            else:
                msg = ("Do you want to save your changes to %s?"
                       % self.name)
            answer = messagebox.askyesnocancel(dialogtitle, msg)
            if answer is None:
                return False
            if answer:
                self.save()
        return True

    def _get_dialog_options(self):
        result = {'filetypes': [("Python files", "*.py"), ("All files", "*")]}
        if self.name is None:
            result['initialdir'] = os.getcwd()
        else:
            result['initialdir'] = os.path.dirname(self.name)
            result['initialfile'] = os.path.basename(self.name)
        return result

    def new_file(self):
        if self.savecheck("New file"):
            self.textwidget.delete('1.0', 'end')
            self.textwidget.edit_modified(False)
            self.textwidget.edit_reset()
            self.name = None
            self.textwidget.do_cursor_move()
            self.textwidget.do_linecount_changed()

    def open_file(self, filename=None):
        if not self.savecheck("Open a file"):
            return

        if filename is None:
            options = self._get_dialog_options()
            filename = filedialog.askopenfilename(**options)
            if not filename:
                # cancel
                return

        try:
            with open(filename, 'r',
                      encoding=self._settings['encoding']) as f:
                content = f.read()
        except (OSError, UnicodeError):
            messagebox.showerror("Opening failed!", traceback.format_exc())
            return

        self.name = filename
        self.textwidget.delete('1.0', 'end')
        self.textwidget.insert('1.0', content)
        self.textwidget.edit_modified(False)
        self.textwidget.edit_reset()
        self.textwidget.do_cursor_move()
        self.textwidget.do_linecount_changed()

    def save(self):
        if self.textwidget.get('end-2c', 'end-1c') != '\n':
            # doesn't end with a \n yet
            if self._settings['add_trailing_newline']:
                # make sure we don't move the cursor, IDLE does it and
                # it's annoying
                here = self.textwidget.index('insert')
                self.textwidget.insert('end-1c', '\n')
                self.textwidget.mark_set('insert', here)
                self.textwidget.do_linecount_changed()

        if self.name is None:
            self.save_as()
            return

        try:
            with _backup_open(self.name, 'w',
                              encoding=self._settings['encoding']) as f:
                f.write(self.textwidget.get('1.0', 'end-1c'))
        except (OSError, UnicodeError):
            messagebox.showerror("Saving failed!", traceback.format_exc())
            return
        self.textwidget.edit_modified(False)

    def save_as(self):
        options = self._get_dialog_options()
        filename = filedialog.asksaveasfilename(**options)
        if filename:
            # not cancelled
            self.name = filename
            self.save()
