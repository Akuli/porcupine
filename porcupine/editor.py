"""The main Editor class."""

import logging
import os
import sys
import tkinter as tk
from tkinter import messagebox
import traceback

from porcupine import __doc__ as init_docstring
from porcupine import dialogs, filetabs, settingeditor, tabs
from porcupine.settings import config, color_themes


log = logging.getLogger(__name__)

DESCRIPTION = '\n\n'.join([
    ' '.join(init_docstring.split()),
    "You can create a new file by pressing Ctrl+N or open an existing "
    "file by pressing Ctrl+O. The file name will be displayed in red "
    "if the file has been changed and you can save the file with "
    "Ctrl+S.",
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


class HandyMenu(tk.Menu):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, tearoff=False, **kwargs)
        self.disablelist = []    # compatible with Editor.disablelist

    def add_handy_command(self, label=None, accelerator=None,
                          command=None, disably=False, **kwargs):
        """Add an item to the menu.

        If disably is True, the menuitem will be disabled when there are
        no tabs in the editor.
        """
        if label is not None:
            kwargs['label'] = label
        if accelerator is not None:
            kwargs['accelerator'] = accelerator
        if command is not None:
            kwargs['command'] = command
        self.add_command(**kwargs)
        if disably:
            self.disablelist.append((self, self.index('end')))


class Editor(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._finddialog = None    # TODO
        self._settingdialog = None

        tabmgr = self.tabmanager = tabs.TabManager(self)
        tabmgr.pack(fill='both', expand=True)
        create_welcome_msg(tabmgr.no_tabs_frame)

        def tabmethod(attribute):
            """Make a function that calls the current tab's method."""
            def result():
                method = getattr(tabmgr.current_tab, attribute)
                return method()
            return result

        def textmethod(attribute):
            """Make a function that calls the current text widget's method."""
            def result():
                method = getattr(tabmgr.current_tab.textwidget, attribute)
                return method()
            return result

        # This will contain (menu, index) pairs.
        self._disablelist = []

        self.menubar = tk.Menu()

        filemenu = HandyMenu(name='filemenu')
        self.menubar.add_cascade(label="File", menu=filemenu)
        add = filemenu.add_handy_command
        add("New file", "Ctrl+N", self.new_file)
        add("Open", "Ctrl+O", self.open_file)
        add("Save", "Ctrl+S", tabmethod('save'), disably=True)
        add("Save as", "Ctrl+Shift+S", tabmethod('save_as'), disably=True)
        filemenu.add_separator()
        add("Close this file", "Ctrl+W", self._close_file, disably=True)
        add("Quit Porcupine", "Ctrl+Q", self.do_quit)
        self._disablelist.extend(filemenu.disablelist)

        editmenu = self._editmenu = HandyMenu()
        self.menubar.add_cascade(label="Edit", menu=editmenu)
        add = editmenu.add_handy_command
        add("Undo", "Ctrl+Z", textmethod('undo'), disably=True)
        add("Redo", "Ctrl+Y", textmethod('redo'), disably=True)
        add("Cut", "Ctrl+X", textmethod('cut'), disably=True)
        add("Copy", "Ctrl+C", textmethod('copy'), disably=True)
        add("Paste", "Ctrl+V", textmethod('paste'), disably=True)
        editmenu.add_separator()
        add("Settings", None, self._show_settings)
        #editmenu.add_separator()
        #add("Find", "Ctrl+F", self.find, disably=True)
        self._disablelist.extend(editmenu.disablelist)

        # right-clicking on a text widget will post the edit menu
        self.bind_all('<Button-1>', lambda event: editmenu.unpost())

        thememenu = HandyMenu()
        self.menubar.add_cascade(label="Color themes", menu=thememenu)

        # the Default theme goes first
        theme_names = color_themes.sections()
        theme_names.sort(key=str.casefold)
        for name in ['Default'] + theme_names:
            thememenu.add_radiobutton(
                label=name, value=name,
                variable=config.variables['editing:color_theme'])

        tabmgr.on_tabs_changed.append(self._tabs_changed)
        self._tabs_changed([])  # disable the menuitems

        def disably(func):
            """Make a function that calls func when there are tabs."""
            def result():
                if tabmgr.tabs:
                    func()
            return result

        # The text widgets are also bound to these because bind_all()
        # doesn't seem to override their default bindings if there are
        # any.
        bindings = tabmgr.bindings + [
            # (keysym, callback)
            ('<Control-n>', self.new_file),
            ('<Control-o>', self.open_file),
            ('<Control-s>', disably(tabmethod('save'))),
            ('<Control-S>', disably(tabmethod('save_as'))),
            ('<Control-w>', disably(self._close_file)),
            ('<Control-q>', self.do_quit),
            ('<Control-z>', disably(textmethod('undo'))),
            ('<Control-y>', disably(textmethod('redo'))),
            ('<Control-x>', disably(textmethod('cut'))),
            ('<Control-c>', disably(textmethod('copy'))),
            ('<Control-v>', disably(textmethod('paste'))),
        ]
        self._bindings = []   # [(keysym, real_callback), ...]
        for keysym, callback in bindings:
            self._add_binding(keysym, callback)

        # See the comments in tabs.py. Binding this here is enough
        # because text widgets don't seem to bind <Alt-SomeDigitHere> by
        # default.
        self.bind_all('<Alt-Key>', tabmgr.on_alt_n)

    # this is in a separate function because of scopes and loops
    # TODO: add link to python FAQ here
    def _add_binding(self, keysym, callback):
        def real_callback(event):
            callback()
            return 'break'

        self.bind_all(keysym, real_callback)
        self._bindings.append((keysym, real_callback))

    def _tabs_changed(self, tablist):
        state = 'normal' if tablist else 'disabled'
        for menu, index in self._disablelist:
            menu.entryconfig(index, state=state)

    def _post_editmenu(self, event):
        self._editmenu.post(event.x_root, event.y_root)

    def new_file(self):
        tab = filetabs.FileTab(self.tabmanager)
        self.tabmanager.add_tab(tab)   # creates the tab's widgets
        tab.textwidget.bind('<Button-3>', self._post_editmenu)

        # some of our keyboard bindings conflict with tkinter's bindings
        # and returning 'break' from a bind_all binding is not enough,
        # so we also need these here
        for binding, callback in self._bindings:
            tab.textwidget.bind(binding, callback)

        self.tabmanager.current_tab = tab
        return tab

    def open_file(self, path=None, *, content=None):
        if path is None:
            # i think it's easier to recurse here than wrap the whole
            # thing in try/except
            for path in dialogs.open_files():
                self.open_file(path, content=content)
            return

        # maybe this file is open already?
        for tab in self.tabmanager.tabs:
            # we don't use == because paths are case-insensitive on
            # windows
            if tab.path is not None and os.path.samefile(path, tab.path):
                self.tabmanager.current_tab = tab
                return

        if content is None:
            try:
                with open(path, 'r', encoding=config['files:encoding']) as f:
                    content = f.read()
            except (OSError, UnicodeError):
                messagebox.showerror("Opening failed!",
                                     traceback.format_exc())
                return

        tab = self.new_file()
        tab.path = path
        tab.textwidget.insert('1.0', content)
        tab.textwidget.edit_reset()   # reset undo/redo
        tab.mark_saved()

    def _close_file(self):
        self.tabmanager.current_tab.close()

    def _show_settings(self):
        if self._settingdialog is not None:
            log.info("setting dialog exists already, showing it")
            self._settingdialog.deiconify()
            return

        log.info("creating a new setting dialog")
        dialog = self._settingdialog = tk.Toplevel()
        dialog.title("Porcupine Settings")
        dialog.protocol('WM_DELETE_WINDOW', dialog.withdraw)
        dialog.transient(self)
        dialog.resizable(False, False)
        edit = settingeditor.SettingEditor(
            dialog, ok_callback=dialog.withdraw)
        edit.pack()

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
