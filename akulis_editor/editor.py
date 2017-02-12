# Copyright (c) 2017 Akuli

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""The main Editor class."""


import contextlib
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import traceback
try:
    from types import SimpleNamespace
except ImportError:
    # Python 3.2.
    from argparse import Namespace as SimpleNamespace

from . import finddialog, linenumbers, scrolling, textwidget


class Editor(tk.Tk):

    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
        self._filename = None
        self._finddialog = None

        if self.settings['window'].getboolean('topbar'):
            self.topbar = tk.Frame(self)
            self.topbar.pack(fill='x')
        else:
            self.topbar = None
        self._currentfilelabel = tk.Label(self, text="New file")
        self._orig_label_fg = self._currentfilelabel['fg']
        self._currentfilelabel.pack()

        textarea = tk.Frame(self)
        textarea.pack(fill='both', expand=True)
        # we need to set width and height to 1 to make sure it's never too
        # large for seeing the statusbar
        self.textwidget = textwidget.EditorText(
            textarea, self, width=1, height=1,
            font=settings['editing']['font'])
        self.textwidget.bind('<<Modified>>', self._update_title)
        if settings['window'].getboolean('linenumbers'):
            self.linenumbers = linenumbers.LineNumbers(
                textarea, self.textwidget, font=settings['editing']['font'])
            scrollbar = scrolling.MultiScrollbar(
                textarea, [self.textwidget, self.linenumbers])
            self.linenumbers.pack(side='left', fill='y')
        else:
            self.linenumbers = linenumbers.DummyLineNumbers()
            scrollbar = tk.Scrollbar(textarea)
            self.textwidget['yscrollcommand'] = scrollbar.set
            scrollbar['command'] = self.textwidget.yview
        self.textwidget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='left', fill='y')

        if settings['window'].getboolean('statusbar'):
            self.statusbar = tk.Label(
                self, anchor='w', relief='sunken', text="Line 1, column 0")
            self.statusbar.pack(fill='x')
        else:
            self.statusbar = None

        menucontent = [
            ("File", [
                ("New file", "Ctrl+N", '<Control-n>', self.new_file),
                ("Open", "Ctrl+O", '<Control-o>', self.open_file),
                ("Save", "Ctrl+S", '<Control-s>', self.save),
                ("Save as", "Ctrl+Shift+S", '<Control-S>', self.save_as),
                None,   # separator
                ("Quit", "Ctrl+Q", '<Control-q>', self.quit_editor),
            ]),
            ("Edit", [
                ("Undo", "Ctrl+Z", '<Control-z>', self.undo),
                ("Redo", "Ctrl+Y", '<Control-y>', self.redo),
                None,
                ("Find", "Ctrl+F", '<Control-f>', self.find),
            ]),
        ]
        menubar = self['menu'] = tk.Menu(self)
        for title, menuitems in menucontent:
            menu = tk.Menu(menubar, tearoff=False)
            for item in menuitems:
                if item is None:
                    menu.add_separator()
                    continue
                text, accelerator, binding, command = item
                menu.add_command(label=text, accelerator=accelerator,
                                 command=command)
                self._bind_menu_command(binding, command)
            menubar.add_cascade(label=title, menu=menu)

        if self.topbar is not None:
            # menucontent[0][1] is the item list of the File menu
            for item in menucontent[0][1]:
                if item is None:
                    # it's a separator, we'll add an empty frame that
                    # fills extra space
                    tk.Frame(self.topbar).pack(side='left', expand=True)
                    continue
                text, accelerator, binding, command = item
                button = tk.Button(self.topbar, text=text, command=command)
                button.pack(side='left')

        self._update_title()
        self.protocol('WM_DELETE_WINDOW', self.quit_editor)
        self.geometry(settings['window']['geometry'])
        self.textwidget.focus()

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, filename):
        self._filename = filename
        self._update_title()

    def _bind_menu_command(self, binding, command):
        def bindcallback(event):
            command()
            return 'break'

        self.bind(binding, bindcallback)
        self.textwidget.bind(binding, bindcallback)

    def _update_title(self, event=None):
        """Update the current file label's text and the editor's title."""
        label = self._currentfilelabel
        if self.filename is None:
            windowtitle = labeltext = "New file"
        else:
            windowtitle = self.filename
            labeltext = "File " + self.filename
        if self.textwidget.edit_modified():
            label['fg'] = 'red'
            labeltext += ", MODIFIED"
        else:
            label['fg'] = self._orig_label_fg
        self.title(windowtitle + " - Akuli's Editor")
        label['text'] = labeltext

    def update_statusbar(self):
        line, column = self.textwidget.index('insert').split('.')
        self.statusbar['text'] = "Line %s, column %s" % (line, column)

    def _open(self, path, mode):
        """Like open(), but uses the settingsuration."""
        return open(path, mode, encoding=self.settings['files']['encoding'])

    @contextlib.contextmanager
    def _backup_open(self, path, mode):
        """Like _open(), but use a backup file if needed."""
        if os.path.exists(path):
            # we can back up
            backuppath = path + '.backup'
            while os.path.exists(backuppath):
                backuppath += '.backup'
            shutil.copy(path, backuppath)
            try:
                yield self._open(path, mode)
            except Exception as e:
                # restore from the backup
                shutil.move(backuppath, path)
                raise e
            # it succeeded, get rid of the backup
            os.remove(backuppath)
        else:
            yield self._open(path, mode)

    def _savecheck(self, dialogtitle):
        """Display a 'wanna save?' dialog and save if necessary.

        Return False if the user cancels and True otherwise.
        """
        if self.textwidget.edit_modified():
            if self.filename is None:
                msg = "Do you want to save your changes?"
            else:
                msg = ("Do you want to save your changes to %s?"
                       % self.filename)
            answer = messagebox.askyesnocancel(dialogtitle, msg)
            if answer is None:
                return False
            if answer:
                self.save()
        return True

    def _get_dialog_options(self):
        result = {'filetypes': [("Python files", '*.py'), ("All files", '*')]}
        if self.filename is None:
            result['initialdir'] = os.getcwd()
        else:
            result['initialdir'] = os.path.dirname(self.filename)
            result['initialfile'] = os.path.basename(self.filename)
        return result

    def new_file(self):
        if self._savecheck("New file"):
            self.textwidget.delete('0.0', 'end')
            self.textwidget.edit_modified(False)
            self.textwidget.edit_reset()
            self.filename = None
            self.update_statusbar()
            self.linenumbers.do_update()

    def open_file(self, filename=None):
        if not self._savecheck("Open a file"):
            return
        if filename is None:
            options = self._get_dialog_options()
            filename = filedialog.askopenfilename(**options)
            if not filename:
                # cancel
                return
        try:
            with self._open(filename, 'r') as f:
                content = f.read()
        except (OSError, UnicodeError):
            messagebox.showerror("Opening failed!", traceback.format_exc())
            return
        self.filename = filename
        self.textwidget.delete('0.0', 'end')
        self.textwidget.insert('0.0', content)
        self.textwidget.highlighter.highlight_all()
        self.textwidget.edit_modified(False)
        self.textwidget.edit_reset()
        self.update_statusbar()
        self.linenumbers.do_update()

    def save(self):
        if self.textwidget.get('end-2c', 'end-1c') != '\n':
            # doesn't end with \n
            if self.settings['files'].getboolean('add-trailing-newline'):
                # make sure we don't move the cursor, it can be annoying
                here = self.textwidget.index('insert')
                self.textwidget.insert('end-1c', '\n')
                self.textwidget.mark_set('insert', here)
                self.linenumbers.do_update()
        if self.settings['files'].getboolean('strip-trailing-whitespace'):
            linecount = int(self.textwidget.index('end-1c').split('.')[0])
            for lineno in range(1, linecount+1):
                self.textwidget.strip_whitespace(lineno)
            self.update_statusbar()

        if self.filename is None:
            # set self.filename and call save() again
            self.save_as()
            return
        try:
            with self._backup_open(self.filename, 'w') as f:
                f.write(self.textwidget.get('0.0', 'end-1c'))
        except (OSError, UnicodeError):
            messagebox.showerror("Saving failed!", traceback.format_exc())
            return
        self.textwidget.edit_modified(False)

    def save_as(self):
        options = self._get_dialog_options()
        filename = filedialog.asksaveasfilename(**options)
        if filename:
            # not cancelled
            self.filename = filename
            self.save()

    def quit_editor(self):
        if self._savecheck("Quit"):
            # I'm not sure what's the difference between quit() and
            # destroy(), but sometimes destroy() gives me weird errors
            # like this one:
            #   alloc: invalid block: 0xa31eef8: 78 a
            #   Aborted
            # I have tried the faulthandler module, but for some reason
            # it doesn't print a traceback... 0_o
            self.quit()

    def undo(self):
        try:
            self.textwidget.edit_undo()
        except tk.TclError:   # nothing to undo
            return
        self.textwidget.highlighter.highlight_all()
        self.linenumbers.do_update()
        self.update_statusbar()

    def redo(self):
        try:
            self.textwidget.edit_redo()
        except tk.TclError:   # nothing to redo
            return
        self.textwidget.highlighter.highlight_all()
        self.linenumbers.do_update()
        self.update_statusbar()

    def find(self):
        if self._finddialog is None:
            self._finddialog = finddialog.FindDialog(self)
        self._finddialog.show()

