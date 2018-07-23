"""The main window and tab manager globals are here."""

import functools
import logging
from queue import Empty         # queue is a handy variable name
import tkinter
import traceback
import webbrowser

from porcupine import (_dialogs, _logs, actions, filetypes, dirs,
                       settings, tabs, utils)

log = logging.getLogger(__name__)

# global state makes some things a lot easier
_root = None
_tab_manager = None
_init_kwargs = {}


# get_main_window() and get_tab_manager() work only if this has been called
def init(verbose_logging=False):
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


def get_init_kwargs():
    """Return a dictionary of the keyword arguments that were passed to :func:\
`init`.

    This is useful for invoking :func:`init` again in exactly the same
    way.
    """
    if not _init_kwargs:
        raise RuntimeError("init() wasn't called")
    return _init_kwargs


def get_main_window():
    """Return the tkinter root window that Porcupine is using."""
    if _root is None:
        raise RuntimeError("Porcupine is not running")
    return _root


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
    corner of the main window.

    First the :meth:`~porcupine.tabs.Tab.can_be_closed` method of each
    tab is called. If all tabs can be closed, a ``<<PorcupineQuit>>``
    virtual event is generated on the main window, all tabs are closed
    with :meth:`~porcupine.tabs.TabManager.close_tab` and widgets are
    destroyed.
    """
    for tab in _tab_manager.tabs():
        if not tab.can_be_closed():
            return
        # the tabs must not be closed here, otherwise some of them
        # are closed if not all tabs can be closed

    _root.event_generate('<<PorcupineQuit>>')
    for tab in _tab_manager.tabs():
        _tab_manager.close_tab(tab)
    _root.destroy()


def _setup_actions():
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

    def close_selected_tab():
        tab = _tab_manager.select()
        if tab.can_be_closed():
            _tab_manager.close_tab(tab)

    # TODO: allow adding separators to menus
    actions.add_command("File/New File", new_file, '<Control-n>')
    actions.add_command("File/Open", open_files, '<Control-o>')
    actions.add_command("File/Save", (lambda: _tab_manager.select().save()),
                        '<Control-s>', tabtypes=[tabs.FileTab])
    actions.add_command("File/Save As...",
                        (lambda: _tab_manager.select().save_as()),
                        '<Control-S>', tabtypes=[tabs.FileTab])

    # TODO: disable File/Quit when there are tabs, it's too easy to hit
    # Ctrl+Q accidentally
    actions.add_command("File/Close", close_selected_tab, '<Control-w>',
                        tabtypes=[tabs.Tab])
    actions.add_command("File/Quit", quit, '<Control-q>')

    # TODO: is Edit the best possible place for this?
    actions.add_command("Edit/Porcupine Settings...", settings.show_dialog)

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


def _iter_queue(queue):
    while True:
        try:
            yield queue.get(block=False)
        except Empty:
            break


def run():
    if _root is None:
        raise RuntimeError("init() wasn't called")

    # the user can change the settings only if we get here, so there's
    # no need to wrap the whole thing in try/with/finally/whatever
    try:
        _root.mainloop()
    finally:
        settings.save()
