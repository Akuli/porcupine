#!/usr/bin/env python3

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

"""This is a really simple text editor for writing Python code.

If you have used something like Notepad, Microsoft Word or LibreOffice
Write before you know how to use this editor. Just make sure you have
Python 3.2 or newer with Tkinter installed and run this.
"""

import argparse
import builtins
import configparser
import contextlib
import keyword
import operator
import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import traceback
try:
    from types import SimpleNamespace
except ImportError:
    # Python 3.2.
    from argparse import Namespace as SimpleNamespace


DEFAULT_CONFIG = '''\
# This is an automatically generated configuration file for Akuli's Editor.
[files]
# The encoding of opened files. Set this to UTF-8 unless you know that
# you need something else.
encoding = UTF-8
# Add a trailing newline to the files? This is recommended.
trailing-newline = yes

# Use these to customize how the editor looks.
[colors]
foreground = white
background = black
string = yellow
keyword = cyan
exception = red
builtin = mediumpurple
comment = gray

# These are used with syntax highlighting.
[regexes]
identifier = \\b%s\\b
comment = #.*$
string = '[^']*[^\\\\]'|"[^"]*[^\\\\]"
multiline-string = """[\\S\\s]*?"""|\'\'\'[\\S\\s]*?\'\'\'

[editing]
# How many spaces to insert when tab is pressed? 0 means tabs instead of
# spaces. Set this to 4 unless you need something else.
indent = 4
# How many undo/redo moves to remember? 0 means that there is no limit.
maxundo = 0
# Display the cursor as a square-shaped block instead of a vertical
# line?
blockcursor = no

[toolbars]
# Add buttons for things in the File menu?
topbar = yes
# Display the current line, column and some other things at the bottom?
statusbar = yes
'''


def _parse_geometry(geometry):
    """Convert tkinter geometry string to (x, y, width, height) tuple."""
    place, x, y = geometry.split('+')
    width, height = map(int, place.split('x'))
    return int(x), int(y), width, height


class FindDialog(tk.Toplevel):

    def __init__(self, editor, **kwargs):
        super().__init__(editor, **kwargs)
        self.editor = editor

        topframe = tk.Frame(self)
        topframe.pack(expand=True, anchor='center')
        label = tk.Label(topframe, text="What do you want to search for?")
        label.pack()
        self.entry = tk.Entry(topframe)
        self.entry.bind('<Return>', lambda event: self.find())
        self.entry.bind('<Escape>', lambda event: self.withdraw())
        self.entry.pack()
        self.notfoundlabel = tk.Label(self, fg='red')
        self.notfoundlabel.pack()
        buttonframe = tk.Frame(self)
        buttonframe.pack(side='bottom', fill='x')

        closebutton = tk.Button(buttonframe, text="Close this dialog",
                                command=self.withdraw)
        closebutton.pack(side='right')
        findbutton = tk.Button(buttonframe, text="Find", command=self.find)
        findbutton.pack(side='right')

        self.entry.focus()
        self.title("Find")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.protocol('WM_DELETE_WINDOW', self.withdraw)

    def show(self):
        self.deiconify()
        self.update_idletasks()   # wait for it to get full size
        editorx, editory, editorwidth, editorheight = _parse_geometry(
            self.editor.geometry())
        width, height = 240, 120
        x = editorx + (editorwidth - width) // 2
        y = editory + (editorheight - height) // 2
        self.geometry('%dx%d+%d+%d' % (width, height, x, y))

    def find(self, what=None):
        self.notfoundlabel['text'] = ''
        text = self.editor.textwidget
        if what is None:
            what = self.entry.get()
            if not what:
                # the user didnt enter anything
                return
        start = text.search(what, 'insert+1c')
        if start:
            end = start + ('+%dc' % len(what))
            text.tag_remove('sel', '0.0', 'end')
            text.tag_add('sel', start, end)
            text.mark_set('insert', start)
            text.see(start)
        else:
            self.notfoundlabel['text'] = "Search string not found :("


class EditorText(tk.Text):

    def __init__(self, master, editor, **kwargs):
        self.editor = editor
        self.settings = editor.settings
        colorsettings = self.settings['colors']
        fg = colorsettings['foreground']
        super().__init__(
            master, foreground=fg, selectbackground=fg,
            insertbackground=fg, background=colorsettings['background'],
            undo=True, maxundo=self.settings['editing'].getint('maxundo'),
            blockcursor=self.settings['editing'].getboolean('blockcursor'),
            **kwargs)

        for name in ['keyword', 'exception', 'builtin', 'string', 'comment']:
            self.tag_config(name, foreground=colorsettings[name])
        # this is a separate tag because multiline strings are
        # highlighted separately
        self.tag_config('multiline-string',
                        foreground=colorsettings['string'])

        self._line_highlights = []  # [(regex, tag), ...]
        # True, False, None and probably some other things are in both
        # keyword.kwlist and dir(builtins). We want builtins to take
        # precedence.
        for name in set(keyword.kwlist) - set(dir(builtins)):
            regex = re.compile(self.settings['regexes']['identifier'] % name)
            self._line_highlights.append((regex, 'keyword'))
        for name in dir(builtins):
            if name.startswith('_'):
                continue
            regex = re.compile(self.settings['regexes']['identifier'] % name)
            value = getattr(builtins, name)
            if isinstance(value, type) and issubclass(value, Exception):
                self._line_highlights.append((regex, 'exception'))
            else:
                self._line_highlights.append((regex, 'builtin'))
        for name in ['string', 'comment']:
            regex = re.compile(self.settings['regexes'][name])
            self._line_highlights.append((regex, name))
        # This will be used for removing old tags in highlight_line().
        # The same tag can be added multiple times, but there's no need
        # to remove it multiple times.
        self._line_highlight_tags = set()
        for regex, tag in self._line_highlights:
            self._line_highlight_tags.add(tag)

        self._multiline_string_regex = re.compile(
            self.settings['regexes']['multiline-string'], flags=re.DOTALL)

        if self.settings['editing'].getint('indent') == 0:
            self._indentprefix = '\t'
        else:
            self._indentprefix = ' ' * self.settings['editing'].getint('indent')

        self.bind('<Key>', self._on_key)
        self.bind('<Control-a>', self._on_ctrl_a)
        self.bind('<BackSpace>', self._on_backspace)
        for key in ('<parenright>', '<bracketright>', '<braceright>'):
            self.bind(key, self._on_closing_brace)
        self.bind('<Tab>', lambda event: self._on_tab(False))
        if self.tk.call('tk', 'windowingsystem') == 'x11':
            self.bind('<ISO_Left_Tab>', lambda event: self._on_tab(True))
        else:
            self.bind('<Shift-Tab>', lambda event: self._on_tab(True))
        self.bind('<Button-1>', self._on_click)

    def _on_ctrl_a(self, event):
        """Select all and return 'break' to stop the event handling."""
        self.tag_add('sel', '0.0', 'end')
        return 'break'     # don't run _on_key

    def _on_backspace(self, event):
        """Dedent and return 'break' if possible, if not call _on_key()."""
        if self._autodedent():
            return 'break'
        self._on_key(event)
        return None

    def _on_closing_brace(self, event):
        """Like _autodedent(), but ignore event and return None."""
        self._autodedent()

    def _on_tab(self, shifted):
        """Indent if shifted, dedent otherwise."""
        if shifted:
            action = self.dedent
        else:
            action = self.indent
        try:
            sel_start, sel_end = self.tag_ranges('sel')
        except ValueError:
            # nothing is selected
            lineno = int(self.index('insert').split('.')[0])
            action(lineno)
        else:
            # something is selected
            first_lineno = int(str(sel_start).split('.')[0])
            last_lineno = int(str(sel_end).split('.')[0])
            for lineno in range(first_lineno, last_lineno + 1):
                action(lineno)
        # indenting: don't insert the default tab
        # dedenting: don't move focus out of this widget
        return 'break'

    def _on_key(self, event):
        # The character is not inserted yet when this runs, so we use
        # after_idle to wait until the event is processed.
        if event.keysym == 'Return':
            # This is here because if we return 'break' from something
            # connected to '<Return>' it's impossible to actually type a
            # newline by pressing Return, but we don't really need to
            # run self.highlight_line().
            self.after_idle(self._autoindent)
            self.after_idle(self._strip_whitespace)
            self.after_idle(self.highlight_multiline)
        else:
            self.after_idle(self.highlight_line)
        self.after_idle(self.editor.update_statusbar)

    def _on_click(self, event):
        self.after_idle(self.editor.update_statusbar)

    def indent(self, lineno):
        """Indent by one level."""
        self.insert('%d.0' % lineno, self._indentprefix)

    def dedent(self, lineno):
        """Unindent by one level if possible."""
        indent = self.settings['editing'].getint('indent')
        start = '%d.0' % lineno
        end = '%d.%d' % (lineno, len(self._indentprefix))
        if self.get(start, end) == self._indentprefix:
            self.delete(start, end)

    def _autoindent(self):
        """Indent the current line automatically if needed."""
        lineno = int(self.index('insert').split('.')[0])
        prevline = self.get('%d.0-1l' % lineno, '%d.0' % lineno)
        # we can't run self._strip_whitespace() first because then we
        # wouldn't know if we are already in a block or not, so we just
        # .rstrip() here instead
        if prevline.rstrip().endswith((':', '(', '[', '{')):
            # start of a new block
            self.indent(lineno)
        # a block continues
        while prevline.startswith(self._indentprefix):
            self.indent(lineno)
            prevline = prevline[len(self._indentprefix):]

    def _autodedent(self):
        """Dedent the current line automatically if needed."""
        lineno = int(self.index('insert').split('.')[0])
        beforethis = self.get('%d.0' % lineno, 'insert')
        if beforethis.isspace():
            self.dedent(lineno)
            return True
        return False

    def _strip_whitespace(self):
        """Strip trailing whitespace from line before cursor."""
        lineno = int(self.index('insert').split('.')[0])
        start = '%d.0-1l' % lineno
        end = '%d.0-1c' % lineno
        old = self.get(start, end)
        new = old.rstrip()
        if old != new:
            self.delete('%d.%d' % (lineno-1, len(new)), end)

    def highlight_line(self, lineno=None):
        """Do all one-line highlighting needed."""
        # This must be fast because this is ran on (almost) every
        # keypress by _on_key().
        if lineno is None:
            # use cursor's line number
            lineno = int(self.index('insert').split('.')[0])
        line_start = '%d.0' % lineno
        line_end = '%d.0+1l' % lineno
        text = self.get(line_start, line_end).rstrip('\n')
        for tag in self._line_highlight_tags:
            self.tag_remove(tag, line_start, line_end)
        for regex, tag in self._line_highlights:
            for match in regex.finditer(text):
                start = '{}.0+{}c'.format(lineno, match.start())
                end = '{}.0+{}c'.format(lineno, match.end())
                self.tag_add(tag, start, end)

    def highlight_multiline(self):
        """Do all multiline highlighting needed.

        Currently only multiline strings need this.
        """
        text = self.get('0.0', 'end-1c')
        self.tag_remove('multiline-string', '0.0', 'end-1c')
        for match in self._multiline_string_regex.finditer(text):
            start, end = map('0.0+{}c'.format, match.span())
            self.tag_add('multiline-string', start, end)

    def highlight_all(self):
        """Highlight everything.

        This call highlight_multiline() once and highlight_line() with
        all possible line numbers.
        """
        linecount = int(self.index('end-1c').split('.')[0])
        for lineno in range(1, linecount + 1):
            self.highlight_line(lineno)
        self.highlight_multiline()


@contextlib.contextmanager
def handle_errors(*errors):
    """Show an error message if an exception is raised.

    This suppresses exceptions, but the yielded value has a success
    attribute that is True if an exception was raised and False
    otherwise.
    """
    result = SimpleNamespace()
    try:
        yield result
    except errors as e:
        messagebox.showerror(type(e).__name__, traceback.format_exc())
        result.success = False
    else:
        result.success = True


FILETYPES = [("Python files", '*.py'), ("All files", '*')]


class Editor(tk.Tk):

    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
        self._filename = None
        self._finddialog = None

        if self.settings['toolbars'].getboolean('topbar'):
            self.topbar = tk.Frame(self)
            self.topbar.pack(fill='x')
        else:
            self.topbar = None
        self._currentfilelabel = tk.Label(self, text="New file")
        self._orig_label_fg = self._currentfilelabel['fg']
        self._currentfilelabel.pack()
        textarea = tk.Frame(self)
        textarea.pack(fill='both', expand=True)
        # we need to set height=1 here to make sure it's never too large
        # for seeing the statusbar
        self.textwidget = EditorText(textarea, self, height=1)
        self.textwidget.bind('<<Modified>>', self._update_top_label)
        self.textwidget.pack(side='left', fill='both', expand=True)
        scrollbar = tk.Scrollbar(textarea)
        scrollbar.pack(side='left', fill='y')
        self.textwidget['yscrollcommand'] = scrollbar.set
        scrollbar['command'] = self.textwidget.yview
        if self.settings['toolbars'].getboolean('statusbar'):
            print("creatin status bar")
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
                ("Redo", "Ctry+Y", '<Control-y>', self.redo),
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
            # menucontent[0][1] is content of the File menu
            for item in menucontent[0][1]:
                if item is None:
                    # it's a separator, we'll add an empty frame that
                    # fills extra space
                    tk.Frame(self.topbar).pack(side='left', expand=True)
                    continue
                text, accelerator, binding, command = item
                button = tk.Button(self.topbar, text=text, command=command)
                button.pack(side='left')

        self.title("Akuli's Editor")
        self.protocol('WM_DELETE_WINDOW', self.quit_editor)
        self.textwidget.focus()

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, filename):
        self._filename = filename
        self._update_top_label()

    def _bind_menu_command(self, binding, command):
        def bindcallback(event):
            command()
            return 'break'

        self.bind(binding, bindcallback)
        self.textwidget.bind(binding, bindcallback)

    def _update_top_label(self, event=None):
        label = self._currentfilelabel
        if self.filename is None:
            text = "New file"
        else:
            text = "File " + self.filename
        if self.textwidget.edit_modified():
            label['fg'] = 'red'
            text += ", MODIFIED"
        else:
            label['fg'] = self._orig_label_fg
        label['text'] = text

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

    def new_file(self):
        if self._savecheck("New file"):
            self.textwidget.delete('0.0', 'end')
            self.textwidget.edit_modified(False)
            self.textwidget.edit_reset()
            self.filename = None

    def open_file(self, filename=None):
        if not self._savecheck("Open a file"):
            return
        if filename is None:
            options = {}
            if self.filename is not None:
                options['initialdir'] = os.path.dirname(self.filename)
            filename = filedialog.askopenfilename(
                filetypes=FILETYPES, **options)
            if not filename:
                # cancel
                return
        with handle_errors(OSError, UnicodeError) as result:
            with self._open(filename, 'r') as f:
                content = f.read()
        if result.success:
            self.filename = filename
            self.textwidget.delete('0.0', 'end')
            self.textwidget.insert('0.0', content)
            self.textwidget.highlight_all()
            self.textwidget.edit_modified(False)
            self.textwidget.edit_reset()

    def save(self):
        if self.textwidget.get('end-2c', 'end-1c') != '\n':
            # doesn't end with \n
            if self.settings['files'].getboolean('trailing-newline'):
                self.textwidget.insert('end-1c', '\n')
        if self.filename is None:
            # set self.filename and call save() again
            self.save_as()
            return
        with handle_errors(OSError, UnicodeError) as result:
            with self._backup_open(self.filename, 'w') as f:
                f.write(self.textwidget.get('0.0', 'end-1c'))
        if result.success:
            self.textwidget.edit_modified(False)

    def save_as(self):
        options = {}
        if self.filename is not None:
            options['initialfile'] = self.filename
        filename = filedialog.asksaveasfilename(
            filetypes=FILETYPES, **options)
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
            pass
        self.textwidget.highlight_all()

    def redo(self):
        try:
            self.textwidget.edit_redo()
        except tk.TclError:   # nothing to redo
            pass
        self.textwidget.highlight_all()

    def find(self):
        if self._finddialog is None:
            self._finddialog = FindDialog(self)
        self._finddialog.show()


CONFIGFILE = os.path.join(os.path.expanduser('~'), '.akulis-editor.ini')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'file', nargs=argparse.OPTIONAL,
        help="open this file when the editor starts")
    parser.add_argument(
        '-d', '--default-config', action='store_true',
        help="create a default ~/.akulis-editor.ini")
    args = parser.parse_args()
    if args.default_config:
        if os.path.exists(CONFIGFILE):
            answer = input("The configuration file exists. Overwrite? [Y/n] ")
            if answer not in {'Y', 'y'}:
                print("Interrupt.")
                return
        with open(CONFIGFILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_CONFIG)
        print("Default configuration was written to %s."
              % CONFIGFILE)
        return

    settings = configparser.ConfigParser(interpolation=None)
    settings.read_string(DEFAULT_CONFIG)
    settings.read([CONFIGFILE])

    editor = Editor(settings)
    editor.title("Akuli's Editor")
    if args.file is not None:
        editor.open_file(args.file)
    editor.mainloop()


if __name__ == '__main__':
    try:
        import faulthandler
        faulthandler.enable()
    except ImportError:
        pass
    main()
