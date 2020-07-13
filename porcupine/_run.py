"""The main window and tab manager globals are here."""

import functools
import logging
import pathlib
import tkinter
from tkinter import filedialog
import traceback
import typing
import webbrowser

from porcupine import _logs, actions, filetypes, dirs, settings, tabs, utils

log = logging.getLogger(__name__)

# global state makes some things a lot easier
_root: typing.Optional[tkinter.Tk] = None
_tab_manager: typing.Optional[tabs.TabManager] = None
_init_kwargs: typing.Dict[str, typing.Any] = {}


# get_main_window() and get_tab_manager() work only if this has been called
def init(verbose_logging: bool = False) -> None:
    """Get everything ready for running Porcupine.

    The *verbose_logging* option corresponds to the ``--verbose``
    argument. Run ``porcu --help`` for more information about it.
    """
    _init_kwargs.update(locals())   # not too hacky IMO

    global _root
    global _tab_manager
    if _root is not None or _tab_manager is not None:
        raise RuntimeError("cannot init() twice")

    dirs.makedirs()
    _logs.setup(verbose_logging)
    _root = tkinter.Tk()
    _root.protocol('WM_DELETE_WINDOW', quit)
    filetypes._init()

    _tab_manager = tabs.TabManager(_root)
    _tab_manager.pack(fill='both', expand=True)
    for binding, callback in _tab_manager.bindings:
        _root.bind(binding, callback, add=True)

    _setup_actions()


# TODO: avoid Any typing
def get_init_kwargs() -> typing.Dict[str, typing.Any]:
    """Return a dictionary of the keyword arguments that were passed to :func:\
`init`.

    This is useful for invoking :func:`init` again in exactly the same
    way.
    """
    if not _init_kwargs:
        raise RuntimeError("init() wasn't called")
    return _init_kwargs


def get_main_window() -> tkinter.Tk:
    """Return the tkinter root window that Porcupine is using."""
    if _root is None:
        raise RuntimeError("Porcupine is not running")
    return _root


def get_tab_manager() -> tabs.TabManager:
    """Return the :class:`porcupine.tabs.TabManager` widget in the main window.
    """  # these are on a separate line because pep-8 line length
    if _tab_manager is None:
        raise RuntimeError("Porcupine is not running")
    return _tab_manager


def quit() -> None:
    """
    Calling this function is equivalent to clicking the X button in the
    corner of the main window.

    First the :meth:`~porcupine.tabs.Tab.can_be_closed` method of each
    tab is called. If all tabs can be closed, a ``<<PorcupineQuit>>``
    virtual event is generated on the main window, all tabs are closed
    with :meth:`~porcupine.tabs.TabManager.close_tab` and widgets are
    destroyed.
    """
    assert _tab_manager is not None
    assert _root is not None

    for tab in _tab_manager.tabs():
        if not tab.can_be_closed():
            return
        # the tabs must not be closed here, otherwise some of them
        # are closed if not all tabs can be closed

    _root.event_generate('<<PorcupineQuit>>')
    for tab in _tab_manager.tabs():
        _tab_manager.close_tab(tab)
    _root.destroy()


def _setup_actions() -> None:
    def new_file() -> None:
        assert _tab_manager is not None
        _tab_manager.add_tab(tabs.FileTab(_tab_manager))

    def open_files() -> None:
        kwargs = filetypes.get_filedialog_kwargs()
        paths: typing.Sequence[str] = filedialog.askopenfilenames(**kwargs)  # type: ignore

        # tkinter returns '' if the user cancels, and i'm arfaid that python
        # devs might "fix" a future version to return None
        if not paths:
            return

        assert _tab_manager is not None
        for path in map(pathlib.Path, paths):
            try:
                tab = tabs.FileTab.open_file(_tab_manager, path)
            except (UnicodeError, OSError) as e:
                log.exception("opening '%s' failed", path)
                utils.errordialog(type(e).__name__, "Opening failed!",
                                  traceback.format_exc())
                continue

            _tab_manager.add_tab(tab)

    def save_file(save_as: bool) -> None:
        assert _tab_manager is not None
        tab = _tab_manager.select()
        assert isinstance(tab, tabs.FileTab)

        if save_as:
            tab.save_as()
        else:
            tab.save()

    def close_selected_tab() -> None:
        assert _tab_manager is not None
        tab = _tab_manager.select()
        assert tab is not None      # handled by tabtypes=[tabs.Tab] below
        if tab.can_be_closed():
            _tab_manager.close_tab(tab)

    # TODO: an API for adding separators to menus nicely? or just recommend
    #       putting related items in a submenu?
    actions.add_command("File/New File", new_file, '<Control-n>')
    actions.add_command("File/Open", open_files, '<Control-o>')
    actions.add_command("File/Save", functools.partial(save_file, False),
                        '<Control-s>', tabtypes=[tabs.FileTab])
    actions.add_command("File/Save As...", functools.partial(save_file, True),
                        '<Control-S>', tabtypes=[tabs.FileTab])

    # TODO: disable File/Quit when there are tabs, it's too easy to hit
    # Ctrl+Q accidentally
    actions.add_command("File/Close", close_selected_tab, '<Control-w>',
                        tabtypes=[tabs.Tab])
    actions.add_command("File/Quit", quit, '<Control-q>')

    # TODO: is Edit the best possible place for this? maybe a Settings menu
    #       that could also contain plugin-specific settings, and maybe even
    #       things like ttk themes and color styles?
    actions.add_command("Edit/Porcupine Settings...", settings.show_dialog)

    def change_font_size(how: str) -> None:
        # TODO: i think there is similar code in a couple other places too
        config = settings.get_section('General')
        if how == 'reset':
            config.reset('font_size')
        else:
            try:
                config['font_size'] += (1 if how == 'bigger' else -1)
            except settings.InvalidValue:
                pass

    # these work only with filetabs because that way the size change is
    # noticable
    actions.add_command(
        "View/Bigger Font", functools.partial(change_font_size, 'bigger'),
        '<Control-plus>', tabtypes=[tabs.FileTab])
    actions.add_command(
        "View/Smaller Font", functools.partial(change_font_size, 'smaller'),
        '<Control-minus>', tabtypes=[tabs.FileTab])
    actions.add_command(
        "View/Reset Font Size", functools.partial(change_font_size, 'reset'),
        '<Control-0>', tabtypes=[tabs.FileTab])

    def add_link(path: str, url: str) -> None:
        def callback() -> None:     # lambda doesn't work for this...
            webbrowser.open(url)    # ...because this returns non-None and mypy

        actions.add_command(path, callback)

    # TODO: porcupine starring button?
    add_link("Help/Porcupine Wiki",
             "https://github.com/Akuli/porcupine/wiki")
    add_link("Help/Report a problem or request a feature",
             "https://github.com/Akuli/porcupine/issues/new")
    add_link("Help/Read Porcupine's code on GitHub",
             "https://github.com/Akuli/porcupine/tree/master/porcupine")

    add_link("Help/Python Help/Free help chat",
             "http://webchat.freenode.net/?channels=%23%23learnpython")
    add_link("Help/Python Help/My Python tutorial",
             "https://github.com/Akuli/python-tutorial/blob/master/README.md")
    add_link("Help/Python Help/Official Python documentation",
             "https://docs.python.org/")


def run() -> None:
    if _root is None:
        raise RuntimeError("init() wasn't called")

    # the user can change the settings only if we get here, so there's
    # no need to wrap the whole thing in try/with/finally/whatever
    try:
        _root.mainloop()
    finally:
        settings.save()
