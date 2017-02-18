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


import os
import tkinter as tk

from . import files


class Editor(tk.Tk):

    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
        self._filename = None
        self._finddialog = None

        if settings['topbar']:
            self.topbar = tk.Frame(self)
            self.topbar.pack(fill='x')
        else:
            self.topbar = None

        self.file = files.File(self, settings)
        self.file.content.pack(fill='both', expand=True)

        menucontent = [
            ("File", [
                ("New file", "Ctrl+N", '<Control-n>', self.file.new_file),
                ("Open", "Ctrl+O", '<Control-o>', self.file.open_file),
                ("Save", "Ctrl+S", '<Control-s>', self.file.save),
                ("Save as", "Ctrl+Shift+S", '<Control-S>', self.file.save_as),
                None,   # separator
                ("Quit", "Ctrl+Q", '<Control-q>', self.quit_editor),
            ]),
            ("Edit", [
                ("Undo", "Ctrl+Z", '<Control-z>', self.file.textwidget.undo),
                ("Redo", "Ctrl+Y", '<Control-y>', self.file.textwidget.redo),
                #None,
                #("Find", "Ctrl+F", '<Control-f>', self.find),
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
                    # fills extra space and pushes buttons after it to
                    # right
                    tk.Frame(self.topbar).pack(side='left', expand=True)
                    continue

                text, accelerator, binding, command = item
                button = tk.Button(self.topbar, text=text, command=command)
                button.pack(side='left')

        self.protocol('WM_DELETE_WINDOW', self.quit_editor)
        self.geometry(settings['default_geometry'])
        self.file.textwidget.focus()

    def _bind_menu_command(self, binding, command):
        def bindcallback(event):
            command()
            return 'break'

        self.bind_all(binding, bindcallback)

    def _get_dialog_options(self):
        result = {'filetypes': [("Python files", '*.py'), ("All files", '*')]}
        if self.filename is None:
            result['initialdir'] = os.getcwd()
        else:
            result['initialdir'] = os.path.dirname(self.filename)
            result['initialfile'] = os.path.basename(self.filename)
        return result

    def quit_editor(self):
        if self.file.savecheck("Quit"):
            # I'm not sure what's the difference between quit() and
            # destroy(), but sometimes destroy() gives me weird errors
            # like this one:
            #   alloc: invalid block: 0xa31eef8: 78 a
            #   Aborted
            # I have tried the faulthandler module, but for some reason
            # it doesn't print a traceback... 0_o
            self.quit()

    # TODO: add find dialog back here
