"""The main window and tab manager globals are here."""

import logging
import tkinter
import types
from typing import Any, Optional, Type

from porcupine import tabs

log = logging.getLogger(__name__)

# global state makes some things a lot easier
_root: Optional[tkinter.Tk] = None
_tab_manager: Optional[tabs.TabManager] = None
_parsed_args: Optional[Any] = None


def _log_tkinter_error(exc: Type[BaseException], val: BaseException, tb: types.TracebackType) -> Any:
    log.error("Error in tkinter callback", exc_info=(exc, val, tb))


# undocumented on purpose, don't use in plugins
def init(args: Any) -> None:
    global _root
    global _tab_manager
    global _parsed_args
    assert _root is None and _tab_manager is None and _parsed_args is None
    assert args is not None

    _parsed_args = args

    _root = tkinter.Tk()
    _root.protocol('WM_DELETE_WINDOW', quit)
    # TODO(typeshed): why ignore comment needed?
    _root.report_callback_exception = _log_tkinter_error  # type: ignore[assignment,misc]

    _tab_manager = tabs.TabManager(_root)
    _tab_manager.pack(fill='both', expand=True)
    for binding, callback in _tab_manager.bindings:
        _root.bind(binding, callback, add=True)


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


def get_parsed_args() -> Any:
    """Return Porcupine's arguments as returned by :func:`argparse.parse_args`."""
    assert _parsed_args is not None
    return _parsed_args


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
