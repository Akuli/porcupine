# this docstring doesn't contain a one-line summary because it's used in
# the welcome message
"""
Porcupine is a simple, beginner-friendly editor for writing Python code.
If you ever used anything like Notepad, Microsoft Word or LibreOffice
Writer before, you will feel right at home.

You can create a new file by pressing Ctrl+N or open an existing file by
pressing Ctrl+O. The file name will be displayed in red if the file has
been changed and you can save the file with Ctrl+S. Then you can run the
file by pressing F5.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""


version_info = (0, 26, 0)        # this is updated with bump.py
__version__ = '%d.%d.%d' % version_info
__author__ = 'Akuli'
__copyright__ = 'Copyright (c) 2017 Akuli'
__license__ = 'MIT'


import functools
import logging
import os
import tkinter as tk
import traceback
import webbrowser

import pygments.styles
import pygments.token

# these are mostly for init(), "import porcupine" isn't guaranteed to
# import any of this
from porcupine import dialogs, dirs, menubar, settingdialog, tabs, utils
from porcupine.settings import config

log = logging.getLogger(__name__)


# this __init__.py uses a global state because that way doing certain
# things is a lot easier, for example, opening a file for editing is
# easy as "porcupine.open_file(path)"
_main_window = None
_tab_manager = None


def get_main_window():
    """Return the widget passed to :func:`~init`."""
    if _main_window is None:
        raise RuntimeError("%s.init() wasn't called" % __name__)
    return _main_window


def get_tab_manager():
    """Return the :class:`porcupine.tabs.TabManager` widget in the main window.
    """  # these are on a separate line because pep-8 line length
    return _tab_manager


def new_file():
    """Add a "New File" tab to the editor."""
    tabmanager = get_tab_manager()
    tabmanager.add_tab(tabs.FileTab(tabmanager))


def open_file(path):
    """Open an existing file in the editor.

    :exc:`UnicodeError` or :exc:`OSError` is raised if the file cannot
    be read.
    """
    with open(path, 'r', encoding=config['Files', 'encoding']) as file:
        content = file.read()

    tabmanager = get_tab_manager()
    tab = tabs.FileTab(tabmanager, content, path=path)
    tabmanager.add_tab(tab)


def add_action(callback, menupath=None, keyboard_shortcut=(None, None),
               tabtypes=(None, tabs.Tab)):
    """Add a keyboard binding and/or a menu item.

    If *menupath* is given, it will be split by the last ``/``. The
    first part will be used to get a menu with
    :meth:`porcupine.menubar.get_menu`, and the end will be used as the
    text of the menu item.

    Keyboard shortcuts can be added too. If given, *keyboard_shortcut*
    should be a two-tuple of a user-readable string and a tkinter
    keyboard binding; for example, ``('Ctrl+S', '<Control-s>')``.

    If defined, the *tabtypes* argument should be an iterable of
    :class:`porcupine.tabs.Tab` subclasses that item can work
    with. If you want to allow no tabs at all, add None to this list.
    The menuitem will be disabled and the binding won't do anything when
    the current tab is not of a compatible type.

    Example::

        def print_hello():
            print("hello")

        editor.add_action(print_hello, "Hello/Hello World")
    """
    tabtypes = tuple((
        # isinstance(None, type(None)) is True
        type(None) if cls is None else cls
        for cls in tabtypes
    ))
    accelerator, binding = keyboard_shortcut
    tabmanager = get_tab_manager()

    if menupath is not None:
        menupath, menulabel = menupath.rsplit('/', 1)
        menu = menubar.get_menu(menupath)
        menu.add_command(label=menulabel, command=callback,
                         accelerator=accelerator)
        menuindex = menu.index('end')

        def tab_changed(new_tab):
            if isinstance(new_tab, tabtypes):
                menu.entryconfig(menuindex, state='normal')
            else:
                menu.entryconfig(menuindex, state='disabled')

        tab_changed(tabmanager.current_tab)
        tabmanager.tab_changed_hook.connect(tab_changed)

    if binding is not None:
        # TODO: check if it's already bound
        def bind_callback(event):
            if isinstance(tabmanager.current_tab, tabtypes):
                callback()
                # try to allow binding keys that are used for other
                # things by default
                return 'break'

        get_main_window().bind(binding, bind_callback)


def _setup_actions():
    tabmanager = get_tab_manager()

    def open_files():
        defaultdir = os.getcwd()      # FIXME
        for path in dialogs.open_files(defaultdir):
            try:
                open_file(path)
            except (OSError, UnicodeError) as e:
                log.exception("opening '%s' failed", path)
                utils.errordialog(type(e).__name__, "Opening failed!",
                                  traceback.format_exc())
                continue

    def close_current_tab():
        tab = get_tab_manager().current_tab
        if tab.can_be_closed():
            tab.close()

    add_action(new_file, "File/New File", ("Ctrl+N", '<Control-n>'))
    add_action(open_files, "File/Open", ("Ctrl+O", '<Control-o>'))
    add_action((lambda: tabmanager.current_tab.save()),
               "File/Save", ("Ctrl+S", '<Control-s>'), tabtypes=[tabs.FileTab])
    add_action((lambda: tabmanager.current_tab.save_as()),
               "File/Save As...", ("Ctrl+Shift+S", '<Control-S>'),
               tabtypes=[tabs.FileTab])
    menubar.get_menu("File").add_separator()

    # TODO: disable File/Quit when there are tabs, it's too easy to hit
    # Ctrl+Q accidentally
    add_action(close_current_tab, "File/Close", ("Ctrl+W", '<Control-w>'),
               tabtypes=[tabs.Tab])
    add_action(quit, "File/Quit", ("Ctrl+Q", '<Control-q>'))

    def textmethod(attribute):
        def result():
            textwidget = tabmanager.current_tab.textwidget
            method = getattr(textwidget, attribute)
            method()
        return result

    # FIXME: bind these in a text widget only, not globally
    add_action(textmethod('undo'), "Edit/Undo", ("Ctrl+Z", '<Control-z>'),
               tabtypes=[tabs.FileTab])
    add_action(textmethod('redo'), "Edit/Redo", ("Ctrl+Y", '<Control-y>'),
               tabtypes=[tabs.FileTab])
    add_action(textmethod('cut'), "Edit/Cut", ("Ctrl+X", '<Control-x>'),
               tabtypes=[tabs.FileTab])
    add_action(textmethod('copy'), "Edit/Copy", ("Ctrl+C", '<Control-c>'),
               tabtypes=[tabs.FileTab])
    add_action(textmethod('paste'), "Edit/Paste", ("Ctrl+V", '<Control-v>'),
               tabtypes=[tabs.FileTab])
    add_action(textmethod('select_all'), "Edit/Select All",
               ("Ctrl+A", '<Control-a>'), tabtypes=[tabs.FileTab])
    menubar.get_menu("Edit").add_separator()

    # TODO: make this a plugin!
    add_action((lambda: tabmanager.current_tab.find()),
               "Edit/Find and Replace", ("Ctrl+F", '<Control-f>'),
               tabtypes=[tabs.FileTab])

    # TODO: make sure that things added by plugins appear here,
    # before the separator and "Porcupine Settings" (see get_menu)
    menubar.get_menu("Edit").add_separator()
    add_action(settingdialog.show, "Edit/Porcupine Settings...")

    menubar.get_menu("Color Themes")   # this goes between Edit and View

    # the font size stuff are bound by the textwidget itself, that's why
    # there are Nones everywhere
    add_action(
        (lambda: tabmanager.current_tab.textwidget.on_wheel('up')),
        "View/Bigger Font", ("Ctrl+Plus", None), tabtypes=[tabs.FileTab])
    add_action(
        (lambda: tabmanager.current_tab.textwidget.on_wheel('down')),
        "View/Smaller Font", ("Ctrl+Minus", None), tabtypes=[tabs.FileTab])
    add_action(
        (lambda: tabmanager.current_tab.textwidget.on_wheel('reset')),
        "View/Reset Font Size", ("Ctrl+Zero", None), tabtypes=[tabs.FileTab])
    menubar.get_menu("View").add_separator()

    def add_link(menupath, url):
        add_action(functools.partial(webbrowser.open, url), menupath)

    # TODO: an about dialog that shows porcupine version, Python version
    #       and where porcupine is installed
    # TODO: porcupine starring button
    add_link("Help/Free help chat",
             "http://webchat.freenode.net/?channels=%23%23learnpython")
    add_link("Help/My Python tutorial",
             "https://github.com/Akuli/python-tutorial/blob/master/README.md")
    add_link("Help/Official Python documentation",
             "https://docs.python.org/")
    menubar.get_menu("Help").add_separator()
    add_link("Help/Porcupine Wiki",
             "https://github.com/Akuli/porcupine/wiki")
    add_link("Help/Report a problem or request a feature",
             "https://github.com/Akuli/porcupine/issues/new")
    add_link("Help/Read Porcupine's code on GitHub",
             "https://github.com/Akuli/porcupine/tree/master/porcupine")

    stylenamevar = tk.StringVar()
    for name in sorted(pygments.styles.get_all_styles()):
        # the command runs config['Editing', 'pygments_style'] = name
        options = {
            'label': name.replace('-', ' ').replace('_', ' ').title(),
            'value': name, 'variable': stylenamevar,
            'command': functools.partial(
                config.__setitem__, ('Editing', 'pygments_style'), name),
        }

        style = pygments.styles.get_style_by_name(name)
        bg = style.background_color

        # styles have a style_for_token() method, but only iterating
        # is documented :( http://pygments.org/docs/formatterdevelopment/
        # i'm using iter() to make sure that dict() really treats
        # the style as an iterable of pairs instead of some other
        # metaprogramming fanciness
        fg = None
        style_infos = dict(iter(style))
        for token in [pygments.token.String, pygments.token.Text]:
            if style_infos[token]['color'] is not None:
                fg = '#' + style_infos[token]['color']
                break
        if fg is None:
            # do like textwidget.ThemedText._set_style does
            fg = (getattr(style, 'default_style', '') or
                  utils.invert_color(bg))

        options['foreground'] = options['activebackground'] = fg
        options['background'] = options['activeforeground'] = bg

        menubar.get_menu("Color Themes").add_radiobutton(**options)

    config.connect('Editing', 'pygments_style', stylenamevar.set,
                   run_now=True)


def _make_welcome_msg(frame):
    description = '\n\n'.join(
        ' '.join(chunk.split())    # convert all whitespace to single spaces
        for chunk in __doc__.split('\n\n')
    )

    inner_frame = tk.Frame(frame)
    inner_frame.place(relx=0.5, rely=0.5, anchor='center')   # float in center
    tk.Label(inner_frame, font=('', 16, ''),
             text="Welcome to Porcupine!\n").pack()
    tk.Label(inner_frame, font=('', 12, ''), text=description).pack()

    def on_resize(event):
        # 0.9 adds little borders
        for label in inner_frame.winfo_children():
            label['wraplength'] = 0.9 * event.width

    frame.bind('<Configure>', on_resize, add=True)


def init(window):
    global _main_window
    global _tab_manager

    assert [_main_window, _tab_manager].count(None) != 1, (
        "porcupine seems to be partially initialized")
    if _main_window is not None:
        raise RuntimeError("%s.init() was called twice" % __name__)
    _main_window = window    # get_main_window() works from now on

    _tab_manager = tabs.TabManager(window)
    _tab_manager.pack(fill='both', expand=True)
    _make_welcome_msg(_tab_manager.no_tabs_frame)
    for binding, callback in _tab_manager.bindings:
        window.bind(binding, callback)

    dirs.makedirs()
    config.load()
    settingdialog.init()

    menubar.init()
    window['menu'] = menubar.get_menu(None)
    _setup_actions()


def quit():
    """If possible, close all tabs and call ``get_main_window().destroy()``.

    .. seealso:: :func:`get_main_window`
    """
    tabmanager = get_tab_manager()
    for tab in tabmanager.tabs:
        if not tab.can_be_closed():
            return
        # the tabs must not be closed here, otherwise some of them
        # are closed if not all tabs can be closed

    # this should destroy all porcupine's widgets, including the
    # tabmanager (destroying it closes all tabs)
    get_main_window().destroy()
