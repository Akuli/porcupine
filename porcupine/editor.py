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
from tkinter import messagebox
import traceback

from porcupine import __doc__ as init_docstring
from porcupine import dialogs, filetabs, tabs
from porcupine.settings import config


class GlobalBinding:
    """Handy helper class for application-wide keyboard bindings."""

    def __init__(self, some_widget, bindingstring, callback):
        self._binding = bindingstring
        self._callback = callback
        self.enabled = False

        some_widget.bind_all(bindingstring, self._real_callback)

    def _real_callback(self, event):
        if not self.enabled:
            return None
        self._callback()
        return 'break'

    def bind_widget(self, widget):
        widget.bind(self._binding, self._real_callback)


DESCRIPTION = '\n\n'.join([
    ' '.join(init_docstring.split()),
    "You can create a new file by pressing Ctrl+N or open an existing "
    "file by pressing Ctrl+O. The file name will be displayed in red "
    "when the file is not saved, and you can press Ctrl+S to save the "
    "file.",
    "See the menus at the top of the editor for other things you can "
    "do and their keyboard shortcuts.",
])


def create_welcome_msg(frame):
    # the texts will be packed closed to each other into this
    innerframe = tk.Frame(frame)
    innerframe.place(relx=0.5, rely=0.5, anchor='center')  # float in center

    titlelabel = tk.Label(innerframe, font='TkDefaultFont 16',
                          text="Welcome to Porcupine!")
    titlelabel.pack()
    desclabel = tk.Label(innerframe, font='TkDefaultFont 12',
                         text=DESCRIPTION)
    desclabel.pack()

    def resize(event):
        for label in [titlelabel, desclabel]:
            label['wraplength'] = event.width * 0.9    # small borders

    frame.bind('<Configure>', resize)


class Editor(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._finddialog = None

        tabmgr = self.tabmanager = tabs.TabManager(self)
        tabmgr.pack(fill='both', expand=True)
        create_welcome_msg(tabmgr.no_tabs_frame)

        menucontent = [
          # (text, contentlist), ...
          ("File", [
            # (text, acceltext, binding, callback, disable), ...
            # if callback is a string it is treated as an attribute
            # of the current file
            # if disable is True the menuitem is disabled when
            # there is no current file
            ("New file", "Ctrl+N", '<Control-n>', self.new_file, False),
            ("Open", "Ctrl+O", '<Control-o>', self.open_file, False),
            ("Save", "Ctrl+S", '<Control-s>', 'save', True),
            ("Save as", "Ctrl+Shift+S", '<Control-S>', 'save_as', True),
            None,   # separator
            ("Close this file", "Ctrl+W", '<Control-w>',
             self._close_file, True),
            ("Quit Porcupine", "Ctrl+Q", '<Control-q>', self.do_quit, False),
          ]),

          ("Edit", [
            ("Undo", "Ctrl+Z", '<Control-z>', 'textwidget.undo', True),
            ("Redo", "Ctrl+Y", '<Control-y>', 'textwidget.redo', True),
            None,
            ("Cut", "Ctrl+X", '<Control-x>', 'textwidget.cut', True),
            ("Copy", "Ctrl+C", '<Control-c>', 'textwidget.copy', True),
            ("Paste", "Ctrl+V", '<Control-v>', 'textwidget.paste', True),
            #None,
            #("Find", "Ctrl+F", '<Control-f>', self.find, True),
          ]),
        ]

        self._menus = {}        # {title: Menu, ...}
        self._disablelist = []  # [(menu, index, globalbinding), ...]
        self._bindings = []     # list of all global bindings

        def current_tab_command(attributes):
            """Return a function that calls the current tab's method."""
            def result():
                # support dots in attribute names
                method = tabmgr.current_tab
                for attribute in attributes.split('.'):
                    method = getattr(method, attribute)
                return method()

            return result

        self.menubar = tk.Menu()
        for title, menuitems in menucontent:
            menu = self._menus[title] = tk.Menu(tearoff=False)
            self.menubar.add_cascade(label=title, menu=menu)

            for index, item in enumerate(menuitems):
                if item is None:
                    menu.add_separator()
                    continue

                text, accelerator, binding, command, disable = item
                if isinstance(command, str):
                    command = current_tab_command(command)
                menu.add_command(label=text, accelerator=accelerator,
                                 command=command)

                global_binding = GlobalBinding(self, binding, command)
                self._bindings.append(global_binding)
                if disable:
                    self._disablelist.append((menu, index, global_binding))
                else:
                    # it's not enabled by default
                    global_binding.enabled = True

        self.bind_all('<Button-1>', self._unpost_editmenu)
        tabmgr.on_tabs_changed.append(self._tabs_changed)
        self._tabs_changed([])

        self.bind_all('<Alt-Key>', self._do_alt_n)
        self.bind_all('<Control-Prior>',
                      lambda event: tabmgr.select_left(roll_over=True))
        self.bind_all('<Control-Next>',
                      lambda event: tabmgr.select_right(roll_over=True))
        self.bind_all('<Control-Shift-Prior>',
                      lambda event: tabmgr.move_left())
        self.bind_all('<Control-Shift-Next>',
                      lambda event: tabmgr.move_right())

    def _do_alt_n(self, event):
        """Select the n'th tab (0 < n < 10)."""
        try:
            n = int(event.keysym)
        except ValueError:
            return
        if 0 < n < 10 and len(self.tabmanager.tabs) >= n:
            self.tabmanager.current_index = n-1

    def _tabs_changed(self, tablist):
        if tablist:
            for menu, index, binding in self._disablelist:
                binding.enabled = True
                menu.entryconfig(index, state='normal')
        else:
            for menu, index, binding in self._disablelist:
                binding.enabled = False
                menu.entryconfig(index, state='disabled')

    def _post_editmenu(self, event):
        self._menus["Edit"].post(event.x_root, event.y_root)

    def _unpost_editmenu(self, event):
        self._menus["Edit"].unpost()

    def new_file(self):
        tab = filetabs.FileTab(self.tabmanager)
        self.tabmanager.add_tab(tab)   # creates the tab's widgets
        tab.textwidget.bind('<Button-3>', self._post_editmenu)

        # some of our keyboard bindings conflict with tkinter's bindings
        # and returning 'break' from a bind_all binding is not enough,
        # so we also need these here
        for binding in self._bindings:
            binding.bind_widget(tab.textwidget)

        self.tabmanager.current_tab = tab
        return tab

    def open_file(self, path=None, *, content=None):
        if path is None:
            path = dialogs.open_file()
            if path is None:
                return

        # maybe this file is open already?
        for tab in self.tabmanager.tabs:
            # we don't use == because paths are case-insensitive on
            # windows
            if tab.path is not None and os.path.samefile(path, tab.path):
                self.tabmanager.current_tab = tab
                return

        if content is None:
            encoding = config['files']['encoding']
            try:
                with open(path, 'r', encoding=encoding) as f:
                    content = f.read()
            except (OSError, UnicodeError):
                messagebox.showerror("Opening failed!",
                                     traceback.format_exc())
                return

        tab = self.new_file()
        tab.path = path
        tab.textwidget.insert('1.0', content)
        tab.mark_saved()

    def _close_file(self):
        self.tabmanager.current_tab.close()

    def do_quit(self):
        for tab in self.tabmanager.tabs:
            if not tab.can_be_closed():
                return
        # I'm not sure what's the difference between quit() and
        # destroy(), but sometimes destroy() gives me weird errors
        # like this one:
        #   alloc: invalid block: 0xa31eef8: 78 a
        #   Aborted
        # I have tried the faulthandler module, but for some reason
        # it doesn't print a traceback... 0_o
        self.quit()

    # TODO: add find dialog back here


# See __main__.py for the code that actally runs this.
