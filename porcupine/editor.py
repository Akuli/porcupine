"""The main Editor class."""

import functools
import logging
import os
import tkinter as tk
import traceback
import webbrowser

from porcupine import __doc__ as init_docstring
from porcupine import dialogs, tabs, utils
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

    frame.bind('<Configure>', resize, add=True)


class Editor(tk.Frame):

    def __init__(self, *args, fullscreen_callback=None, **kwargs):
        super().__init__(*args, **kwargs)

        tabmgr = self.tabmanager = tabs.TabManager(self)
        tabmgr.pack(fill='both', expand=True)
        create_welcome_msg(tabmgr.no_tabs_frame)

        self.new_tab_hook = tabmgr.new_tab_hook
        self.tab_changed_hook = utils.ContextManagerHook(__name__)

        self.menubar = tk.Menu(tearoff=False)
        self._submenus = {}     # {(parentmenu, label): submenu, ...}
        self.get_menu("Help")   # see comments in get_menu()

        add = self.add_action
        add(self.new_file, "File/New File", "Ctrl+N", '<Control-n>')
        add(self.open_file, "File/Open", "Ctrl+O", '<Control-o>')
        add((lambda: tabmgr.current_tab.save()), "File/Save", "Ctrl+S",
            '<Control-s>', [tabs.FileTab])
        add((lambda: tabmgr.current_tab.save_as()), "File/Save As...",
            "Ctrl+Shift+S", '<Control-S>', [tabs.FileTab])
        self.get_menu("File").add_separator()
        # TODO: rename to 'File/Quit' when possible?
        add(self._close_tab_or_quit, "File/Close", "Ctrl+W", '<Control-w>')

        def textmethod(attribute):
            def result():
                method = getattr(tabmgr.current_tab.textwidget, attribute)
                method()
            return result

        add(textmethod('undo'), "Edit/Undo", "Ctrl+Z", '<Control-z>',
            [tabs.FileTab])
        add(textmethod('redo'), "Edit/Redo", "Ctrl+Y", '<Control-y>',
            [tabs.FileTab])
        add(textmethod('cut'), "Edit/Cut", "Ctrl+X", '<Control-x>',
            [tabs.FileTab])
        add(textmethod('copy'), "Edit/Copy", "Ctrl+C", '<Control-c>',
            [tabs.FileTab])
        add(textmethod('paste'), "Edit/Paste", "Ctrl+V", '<Control-v>',
            [tabs.FileTab])
        add(textmethod('select_all'), "Edit/Select All",
            "Ctrl+A", '<Control-a>', [tabs.FileTab])
        self.get_menu("Edit").add_separator()
        # TODO: make this a plugin
        add((lambda: tabmgr.current_tab.find()), "Edit/Find and Replace",
            "Ctrl+F", '<Control-f>', [tabs.FileTab])

        # FIXME: update the setting dialog
        thememenu = self.get_menu("Settings/Color Themes")
        add((lambda: print("lol")), "Settings/Porcupine Settings...")

        def link(menupath, url):
            callback = functools.partial(webbrowser.open, url)
            self.add_action(callback, menupath)

        # TODO: porcupine starring button
        link("Help/Free help chat",
             "http://webchat.freenode.net/?channels=%23%23learnpython")
        link("Help/My Python tutorial",
             "https://github.com/Akuli/python-tutorial/blob/master/README.md")
        link("Help/Official Python documentation", "https://docs.python.org/")
        self.get_menu("Help").add_separator()
        link("Help/Porcupine Wiki", "https://github.com/Akuli/porcupine/wiki")
        link("Help/Report a problem or request a feature",
             "https://github.com/Akuli/porcupine/issues/new")
        link("Help/Read Porcupine's code",
             "https://github.com/Akuli/porcupine/tree/master/porcupine")

        # the Default theme goes first
        themevar = tk.StringVar()
        themenames = sorted(color_themes.sections(), key=str.casefold)
        for name in ['Default'] + themenames:
            # set_this_theme() runs config['Editing', 'color_theme'] = name
            set_this_theme = functools.partial(
                config.__setitem__, ('Editing', 'color_theme'), name)
            thememenu.add_radiobutton(
                label=name, value=name, variable=themevar,
                command=set_this_theme)
        config.connect('Editing', 'color_theme', themevar.set, run_now=True)

        tabmgr.tab_changed_hook.connect(self._tab_changed)
        self._tab_context_manager = None   # this is lol, see _tab_changed()
        self._tab_changed(None)

        for binding, callback in tabmgr.bindings:
            self.add_action(callback, binding=binding)

    def get_menu(self, label_path):
        """Return a submenu from the menubar.

        The submenu will be created if it doesn't exist already. The
        *label_path* should be a ``/``-separated string of menu labels;
        for example, ``'File/Stuff'`` is a Stuff submenu under the File
        menu.
        """
        menu = self.menubar
        for label in label_path.split('/'):
            try:
                menu = self._submenus[(menu, label)]
            except KeyError:
                submenu = tk.Menu(tearoff=False)
                if menu is self.menubar:
                    # the help menu is always last, like in most other programs
                    index = menu.index('end')
                    if index is None:
                        # there's nothing in the menu bar yet, we're
                        # adding the help menu now
                        index = 0
                    menu.insert_cascade(index, label=label, menu=submenu)
                else:
                    menu.add_cascade(label=label, menu=submenu)

                self._submenus[(menu, label)] = submenu
                menu = submenu

        return menu

    def add_action(self, callback, menupath=None, accelerator=None,
                   binding=None, tabtypes=(None, tabs.Tab)):
        """Add a keyboard binding and/or a menu item.

        If *menupath* is given, it will be split by the last ``/``. The
        first part will be used to get a menu with :meth:`~get_menu`,
        and the end will be used as the text of the menu item.

        Keyboard shortcuts can be added too. If given, *accelerator*
        should be a user-readable string and *binding* should be a
        tkinter keyboard binding.

        If defined, the *tabtypes* argument should be an iterable of
        :class:`porcupine.tabs.Tab` subclasses that this item can work
        with. If you want to allow no tabs at all, add None to this
        list. The menuitem will be disabled and the binding won't do
        anything when the current tab is not of a compatible type.

        Example::

            def print_hello():
                print("hello")

            editor.add_action(callback, menupath="LOL/Do LOL")
        """
        tabtypes = tuple((
            # isinstance(None, type(None)) is True
            type(None) if cls is None else cls
            for cls in tabtypes
        ))

        if menupath is not None:
            menupath, menulabel = menupath.rsplit('/', 1)
            menu = self.get_menu(menupath)
            menu.add_command(label=menulabel, command=callback,
                             accelerator=accelerator)
            menuindex = menu.index('end')

            def tab_changed(new_tab):
                if isinstance(new_tab, tabtypes):
                    menu.entryconfig(menuindex, state='normal')
                else:
                    menu.entryconfig(menuindex, state='disabled')

            tab_changed(self.tabmanager.current_tab)
            self.tabmanager.tab_changed_hook.connect(tab_changed)

        if binding is not None:
            # TODO: check if it's already bound
            def bind_callback(event):
                if isinstance(self.tabmanager.current_tab, tabtypes):
                    callback()
                    # try to allow binding keys that are used for other
                    # things by default, see also add_bindings()
                    return 'break'

            self.bind(binding, bind_callback)

    def _tab_changed(self, new_tab):
        if self._tab_context_manager is not None:
            # not running this for the first time
            self._tab_context_manager.__exit__(None, None, None)

        self._tab_context_manager = self.tab_changed_hook.run(new_tab)
        self._tab_context_manager.__enter__()

    def _post_editmenu(self, event):
        self.editmenu.tk_popup(event.x_root, event.y_root)

    def _add_file_tab(self, tab):
        # TODO: move the binding stuff to FileTab.__init__ or something?
        self.tabmanager.add_tab(tab)
        tab.textwidget.bind('<Button-3>', self._post_editmenu)
        utils.copy_bindings(self, tab.textwidget)
        self.tabmanager.current_tab = tab

    def new_file(self):
        tab = tabs.FileTab(self.tabmanager)
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
            if (isinstance(path, tabs.FileTab)
                    and tab.path is not None
                    and os.path.samefile(path, tab.path)):
                self.tabmanager.current_tab = tab
                return

        tab = tabs.FileTab(self.tabmanager)
        tab.path = path

        if content is None:
            try:
                encoding = config['Files', 'encoding']
                with open(path, 'r', encoding=encoding) as f:
                    for line in f:
                        tab.textwidget.insert('end - 1 char', line)
            except (OSError, UnicodeError) as e:
                log.exception("opening '%s' failed", path)
                utils.errordialog(type(e).__name__, "Opening failed!",
                                  traceback.format_exc())
                return
        else:
            tab.textwidget.insert('1.0', content)

        tab.textwidget.edit_reset()   # reset undo/redo
        tab.mark_saved()
        self._add_file_tab(tab)

    def _close_tab_or_quit(self):
        tab = self.tabmanager.current_tab
        if tab is None:
            # no more tabs
            self.do_quit()
        elif tab.can_be_closed():
            tab.close()

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
