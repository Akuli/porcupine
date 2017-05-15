"""The main Editor class."""

import functools
import logging
import os
import tkinter as tk
from tkinter import messagebox
import traceback
import webbrowser

from porcupine import __doc__ as init_docstring
from porcupine import dialogs, filetabs, settingeditor, tabs, terminal, utils
from porcupine.settings import config, color_themes


log = logging.getLogger(__name__)


def _get_description():
    parts = []
    for part in init_docstring.split('\n\n'):
        parts.append(' '.join(part.split()))
    return '\n\n'.join(parts)


def create_welcome_msg(frame):
    # the texts will be packed closed to each other into this
    innerframe = tk.Frame(frame)
    innerframe.place(relx=0.5, rely=0.5, anchor='center')  # float in center

    titlelabel = tk.Label(innerframe, font='TkDefaultFont 16',
                          text="Welcome to Porcupine!")
    titlelabel.pack()
    desclabel = tk.Label(innerframe, font='TkDefaultFont 12',
                         text=_get_description())
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

    def add_linky_command(self, label, url):
        callback = functools.partial(webbrowser.open, url)
        self.add_command(label=label, command=callback)


class Editor(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._settingdialog = None

        tabmgr = self.tabmanager = tabs.TabManager(self)
        tabmgr.pack(fill='both', expand=True)
        create_welcome_msg(tabmgr.no_tabs_frame)

        self.new_tab_hook = tabmgr.new_tab_hook
        self.tab_changed_hook = utils.ContextManagerHook(__name__)

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

        self.filemenu = HandyMenu()
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        add = self.filemenu.add_handy_command
        add("New file", "Ctrl+N", self.new_file)
        add("Open", "Ctrl+O", self.open_file)
        add("Save", "Ctrl+S", tabmethod('save'), disably=True)
        add("Save as", "Ctrl+Shift+S", tabmethod('save_as'), disably=True)
        add("Run", "F5", self._run_file, disably=True)
        self.filemenu.add_separator()
        add("Close this file", "Ctrl+W", self._close_file, disably=True)
        add("Quit Porcupine", "Ctrl+Q", self.do_quit)
        self._disablelist.extend(self.filemenu.disablelist)

        self.editmenu = self.editmenu = HandyMenu()
        self.menubar.add_cascade(label="Edit", menu=self.editmenu)
        add = self.editmenu.add_handy_command
        add("Undo", "Ctrl+Z", textmethod('undo'), disably=True)
        add("Redo", "Ctrl+Y", textmethod('redo'), disably=True)
        add("Cut", "Ctrl+X", textmethod('cut'), disably=True)
        add("Copy", "Ctrl+C", textmethod('copy'), disably=True)
        add("Paste", "Ctrl+V", textmethod('paste'), disably=True)
        add("Select all", "Ctrl+A", textmethod('select_all'), disably=True)
        add("Find and replace", "Ctrl+F", tabmethod('find'), disably=True)
        self.editmenu.add_separator()
        add("Settings", None, self._show_settings)
        self._disablelist.extend(self.editmenu.disablelist)

        self.thememenu = HandyMenu()
        self.menubar.add_cascade(label="Color themes", menu=self.thememenu)

        # the Default theme goes first
        themevar = tk.StringVar()
        themenames = sorted(color_themes.sections(), key=str.casefold)
        for name in ['Default'] + themenames:
            set_this_theme = functools.partial(
                config.set, 'Editing', 'color_theme', name)
            self.thememenu.add_radiobutton(
                label=name, value=name, variable=themevar,
                command=set_this_theme)
        config.connect('Editing', 'color_theme', themevar.set)

        self.helpmenu = HandyMenu()
        self.menubar.add_cascade(label="Help", menu=self.helpmenu)
        add = self.helpmenu.add_linky_command
        add("Free help chat",
            "http://webchat.freenode.net/?channels=%23%23learnpython")
        add("My Python tutorial",
            "https://github.com/Akuli/python-tutorial/blob/master/README.md")
        add("Official Python documentation", "https://docs.python.org/")
        self.helpmenu.add_separator()
        # TODO: starring button
        add("Porcupine Wiki", "https://github.com/Akuli/porcupine/wiki")
        add("Report a problem or request a feature",
            "https://github.com/Akuli/porcupine/issues/new")
        add("Read Porcupine's code",
            "https://github.com/Akuli/porcupine/tree/master/porcupine")

        tabmgr.tab_changed_hook.connect(self._tab_changed)
        self._tab_context_manager = None   # this is lol, see _tab_changed()
        self._tab_changed(None)

        def disably(func):
            """Make a function that calls func when there are tabs."""
            def result():
                if tabmgr.tabs:
                    func()
            return result

        # The text widgets are also bound to these because bind_all()
        # doesn't seem to override their default bindings if there are
        # any. See _add_file_tab().
        bindings = tabmgr.bindings + [
            ('<Control-n>', self.new_file),
            ('<Control-o>', self.open_file),
            ('<Control-s>', disably(tabmethod('save'))),
            ('<Control-S>', disably(tabmethod('save_as'))),
            ('<Control-w>', disably(self._close_file)),
            ('<Control-q>', self.do_quit),
            ('<Control-f>', disably(tabmethod('find'))),
            ('<F5>', disably(self._run_file)),
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

    def _tab_changed(self, new_tab):
        state = 'normal' if self.tabmanager.tabs else 'disabled'
        for menu, index in self._disablelist:
            menu.entryconfig(index, state=state)

        if self._tab_context_manager is not None:
            # not running this for the first time
            self._tab_context_manager.__exit__(None, None, None)

        self._tab_context_manager = self.tab_changed_hook.run(new_tab)
        self._tab_context_manager.__enter__()

    def _post_editmenu(self, event):
        self.editmenu.tk_popup(event.x_root, event.y_root)

    def _add_file_tab(self, tab):
        self.tabmanager.add_tab(tab)
        tab.textwidget.bind('<Button-3>', self._post_editmenu)

        # some of our keyboard bindings conflict with tkinter's bindings
        # and returning 'break' from a bind_all binding is not enough,
        # so we also need these here
        for binding, callback in self._bindings:
            tab.textwidget.bind(binding, callback)

        self.tabmanager.current_tab = tab

    def new_file(self):
        tab = filetabs.FileTab(self.tabmanager)
        self._add_file_tab(tab)
        return tab

    def open_file(self, path=None, *, content=None):
        if path is None:
            try:
                defaultdir = os.path.dirname(self.tabmanager.current_tab.path)
            except AttributeError:
                defaultdir = None

            # i think it's easier to recurse here than wrap the whole
            # thing in a for loop
            for path in dialogs.open_files(self, defaultdir):
                self.open_file(path, content=content)
            return

        # maybe this file is open already?
        for tab in self.tabmanager.tabs:
            # we don't use == because paths are case-insensitive on
            # windows
            if (isinstance(path, filetabs.FileTab)
              and tab.path is not None
              and os.path.samefile(path, tab.path)):
                self.tabmanager.current_tab = tab
                return

        tab = filetabs.FileTab(self.tabmanager)
        tab.path = path

        if content is None:
            try:
                encoding = config['Files']['encoding']
                with open(path, 'r', encoding=encoding) as f:
                    for line in f:
                        tab.textwidget.insert('end-1c', line)
            except (OSError, UnicodeError):
                log.exception("opening '%s' failed", path)
                messagebox.showerror("Opening failed!",
                                     traceback.format_exc())
                return
        else:
            tab.textwidget.insert('1.0', content)

        tab.textwidget.edit_reset()   # reset undo/redo
        tab.mark_saved()
        self._add_file_tab(tab)

    def _close_file(self):
        tab = self.tabmanager.current_tab
        if tab.can_be_closed():
            tab.close()

    # TODO: turn this into a plugin
    def _run_file(self):
        filetab = self.tabmanager.current_tab
        if filetab.path is None or not filetab.is_saved():
            filetab.save()
        if filetab.path is None:
            # user cancelled a save as dialog
            return
        terminal.run(filetab.path)

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
