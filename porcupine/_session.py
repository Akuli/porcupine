import functools
import logging
import traceback
import webbrowser

import pygments.styles
import pygments.token

import porcupine
from porcupine import _dialogs, actions, dirs, filetypes, settings, tabs, utils

log = logging.getLogger(__name__)

# global state makes some things a lot easier
_main_window = None
_tab_manager = None


# get_main_window() and get_tab_manager() work only if this has been called
def init(main_window, tab_manager):
    global _main_window
    global _tab_manager

    assert _main_window is None and _tab_manager is None
    _main_window = main_window
    _tab_manager = tab_manager


def get_main_window():
    """Return the tkinter root window that Porcupine is using."""
    if _main_window is None:
        raise RuntimeError("Porcupine is not running")
    return _main_window


def get_tab_manager():
    """Return the :class:`porcupine.tabs.TabManager` widget in the main window.
    """  # these are on a separate line because pep-8 line length
    if _tab_manager is None:
        raise RuntimeError("Porcupine is not running")
    return _tab_manager


# TODO: add some way to run callbacks when this function is called
def quit():
    """
    Calling this function is equivalent to clicking the X button in the
    corner of the window.

    First the :meth:`~porcupine.tabs.Tab.can_be_closed` method of each
    tab is called. If all tabs can be closed, a ``<<PorcupineQuit>>``
    virtual event is generated on the main window, all tabs are closed
    with :meth:`~porcupine.tabs.TabManager.close_tab` and widgets are
    destroyed.
    """
    for tab in _tab_manager.tabs:
        if not tab.can_be_closed():
            return
        # the tabs must not be closed here, otherwise some of them
        # are closed if not all tabs can be closed

    _main_window.event_generate('<<PorcupineQuit>>')

    # closing tabs removes them from the tabs list, that's why copying
    for tab in _tab_manager.tabs.copy():
        _tab_manager.close_tab(tab)

    # all widgets are in the main window, so destroying the main window
    # should destroy everything
    _main_window.destroy()


def setup_actions():
    def new_file():
        _tab_manager.add_tab(tabs.FileTab(_tab_manager))

    def open_files():
        for path in _dialogs.open_files():
            try:
                tab = tabs.FileTab.open_file(_tab_manager, path)
            except (UnicodeError, OSError) as e:
                log.exception("opening '%s' failed", path)
                utils.errordialog(type(e).__name__, "Opening failed!",
                                  traceback.format_exc())
                continue

            _tab_manager.add_tab(tab)

    def close_current_tab():
        if _tab_manager.current_tab.can_be_closed():
            _tab_manager.close_tab(_tab_manager.current_tab)

    # TODO: allow adding separators to menus
    actions.add_command("File/New File", new_file, '<Control-n>')
    actions.add_command("File/Open", open_files, '<Control-o>')
    actions.add_command("File/Save", (lambda: _tab_manager.current_tab.save()),
                        '<Control-s>', tabtypes=[tabs.FileTab])
    actions.add_command("File/Save As...",
                        (lambda: _tab_manager.current_tab.save_as()),
                        '<Control-S>', tabtypes=[tabs.FileTab])

    # TODO: disable File/Quit when there are tabs, it's too easy to hit
    # Ctrl+Q accidentally
    actions.add_command("File/Close", close_current_tab, '<Control-w>',
                        tabtypes=[tabs.Tab])
    actions.add_command("File/Quit", quit, '<Control-q>')

    # TODO: is Edit the best possible place for this?
    actions.add_command(
        "Edit/Porcupine Settings...",
        functools.partial(settings.show_dialog, porcupine.get_main_window()))

    def change_font_size(how):
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
    # TODO: maybe these shouldn't be bound globally?
    actions.add_command(
        "View/Bigger Font", functools.partial(change_font_size, 'bigger'),
        '<Control-plus>', tabtypes=[tabs.FileTab])
    actions.add_command(
        "View/Smaller Font", functools.partial(change_font_size, 'smaller'),
        '<Control-minus>', tabtypes=[tabs.FileTab])
    actions.add_command(
        "View/Reset Font Size", functools.partial(change_font_size, 'reset'),
        '<Control-0>', tabtypes=[tabs.FileTab])

    def add_link(path, url):
        actions.add_command(path, functools.partial(webbrowser.open, url))

    # TODO: an about dialog that shows porcupine version, Python version
    #       and where porcupine is installed
    # TODO: porcupine starring button
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
