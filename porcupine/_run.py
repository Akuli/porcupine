"""The main window and tab manager globals are here."""

import logging
import tkinter
import types
from typing import Any, Dict, Optional, Type

from porcupine import _logs, filetypes, dirs, menubar, settings, tabs

log = logging.getLogger(__name__)

# global state makes some things a lot easier
_root: Optional[tkinter.Tk] = None
_tab_manager: Optional[tabs.TabManager] = None
_init_kwargs: Dict[str, Any] = {}


def _log_tkinter_error(exc: Type[BaseException], val: BaseException, tb: types.TracebackType) -> Any:
    log.error("Error in tkinter callback", exc_info=(exc, val, tb))


# get_main_window() and get_tab_manager() work only if this has been called
# TODO: should this function call pluginloader.load()?
def init(*, verbose_logging: bool = False) -> None:
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
    # TODO: why ignore comment needed?
    _root.report_callback_exception = _log_tkinter_error  # type: ignore[assignment,misc]
    settings._init()
    filetypes._init()

    _tab_manager = tabs.TabManager(_root)
    _tab_manager.pack(fill='both', expand=True)
    for binding, callback in _tab_manager.bindings:
        _root.bind(binding, callback, add=True)

    menubar._init()


# TODO: avoid Any typing
def get_init_kwargs() -> Dict[str, Any]:
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


def run() -> None:
    if _root is None:
        raise RuntimeError("init() wasn't called")

    # the user can change the settings only if we get here, so there's
    # no need to wrap the whole thing in try/with/finally/whatever
    try:
        _root.mainloop()
    finally:
        settings.save()


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
