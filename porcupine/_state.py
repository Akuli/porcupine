"""The main window and tab manager globals are here."""
from __future__ import annotations

import logging
import tkinter
import types
from tkinter import ttk
from typing import Any, Type

from porcupine import settings, tabs

log = logging.getLogger(__name__)

# global state makes some things a lot easier (I'm sorry)
_root: tkinter.Tk | None = None
_paned_window: ttk.Panedwindow | None = None
_tab_manager: tabs.TabManager | None = None
_parsed_args: Any | None = None  # Any | None means you have to check if its None
filedialog_kwargs: dict[str, Any] = {}


def _log_tkinter_error(
    exc: Type[BaseException], val: BaseException, tb: types.TracebackType | None
) -> Any:
    log.error("Error in tkinter callback", exc_info=(exc, val, tb))


# undocumented on purpose, don't use in plugins
def init(args: Any) -> None:
    global _root
    global _tab_manager
    global _parsed_args
    global _paned_window
    assert _root is None and _tab_manager is None and _parsed_args is None and _paned_window is None
    assert args is not None

    log.debug("init() starts")
    _parsed_args = args

    _root = tkinter.Tk(className="Porcupine")  # class name shows up in my alt+tab list
    log.debug("root window created")
    log.debug("Tcl/Tk version: " + _root.tk.eval("info patchlevel"))

    _root.protocol("WM_DELETE_WINDOW", quit)
    _root.report_callback_exception = _log_tkinter_error

    _paned_window = ttk.Panedwindow(_root, orient="horizontal")
    settings.remember_divider_positions(_paned_window, "main_panedwindow_dividers", [250])
    _root.bind(
        "<<PluginsLoaded>>",
        lambda event: get_paned_window().event_generate("<<DividersFromSettings>>"),
        add=True,
    )
    _paned_window.pack(fill="both", expand=True)

    _tab_manager = tabs.TabManager(_paned_window)
    _paned_window.add(_tab_manager)

    log.debug("init() done")


def get_main_window() -> tkinter.Tk:
    """Return the tkinter root window that Porcupine is using."""
    if _root is None:
        raise RuntimeError("Porcupine is not running")
    return _root


def get_tab_manager() -> tabs.TabManager:
    """Return the :class:`porcupine.tabs.TabManager` widget in the main window."""
    if _tab_manager is None:
        raise RuntimeError("Porcupine is not running")
    return _tab_manager


# TODO: document available attributes
def get_parsed_args() -> Any:
    """Return Porcupine's arguments as returned by :func:`argparse.parse_args`."""
    assert _parsed_args is not None
    return _parsed_args


def get_paned_window() -> ttk.Panedwindow:
    if _paned_window is None:
        raise RuntimeError("Porcupine is not running")
    return _paned_window


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

    _root.event_generate("<<PorcupineQuit>>")
    for tab in _tab_manager.tabs():
        _tab_manager.close_tab(tab)
    _root.destroy()
