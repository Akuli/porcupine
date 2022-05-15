"""The main window and tab manager globals are here."""
from __future__ import annotations

import dataclasses
import logging
import os
import platform
import sys
import tkinter
import types
from typing import Any, Type

from porcupine import images, tabs, utils

# Windows resolution
if sys.platform == "win32":
    from ctypes import windll

    windows_version = platform.release()
    try:
        windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        # Windows 7 or older
        windll.user32.SetProcessDPIAware()

log = logging.getLogger(__name__)


@dataclasses.dataclass
class _State:
    root: tkinter.Tk
    horizontal_panedwindow: utils.PanedWindow
    vertical_panedwindow: utils.PanedWindow
    tab_manager: tabs.TabManager
    parsed_args: Any  # not None


# global state makes some things a lot easier (I'm sorry)
_global_state: _State | None = None
filedialog_kwargs: dict[str, Any] = {}


def _log_tkinter_error(
    exc: Type[BaseException], val: BaseException, tb: types.TracebackType | None
) -> Any:
    log.error("Error in tkinter callback", exc_info=(exc, val, tb))


# undocumented on purpose, don't use in plugins
def init(args: Any) -> None:
    assert args is not None

    global _global_state
    assert _global_state is None

    log.debug("init() starts")

    root = tkinter.Tk(className="Porcupine")  # class name shows up in my alt+tab list
    log.debug("root window created")
    log.debug("Tcl/Tk version: " + root.tk.eval("info patchlevel"))

    root.protocol("WM_DELETE_WINDOW", quit)

    # Don't set up custom error handler while testing https://stackoverflow.com/a/58866220
    if "PYTEST_CURRENT_TEST" not in os.environ:
        root.report_callback_exception = _log_tkinter_error

    horizontal_pw = utils.PanedWindow(root, orient="horizontal")
    horizontal_pw.pack(fill="both", expand=True)

    vertical_pw = utils.PanedWindow(horizontal_pw, orient="vertical")
    horizontal_pw.add(vertical_pw)

    tab_manager = tabs.TabManager(vertical_pw)
    vertical_pw.add(tab_manager, stretch="always")

    tab_manager.bind("<<ThemeChanged>>", images._update_dark_or_light_images, add=True)

    _global_state = _State(
        root=root,
        horizontal_panedwindow=horizontal_pw,
        vertical_panedwindow=vertical_pw,
        tab_manager=tab_manager,
        parsed_args=args,
    )
    log.debug("init() done")


def _get_state() -> _State:
    if _global_state is None:
        raise RuntimeError("Porcupine is not running")
    return _global_state


def get_main_window() -> tkinter.Tk:
    """Return the tkinter root window that Porcupine is using."""
    return _get_state().root


def get_tab_manager() -> tabs.TabManager:
    """Return the :class:`porcupine.tabs.TabManager` widget in the main window."""
    return _get_state().tab_manager


# TODO: document available attributes
def get_parsed_args() -> Any:
    """Return Porcupine's arguments as returned by :func:`argparse.parse_args`."""
    return _get_state().parsed_args


def get_horizontal_panedwindow() -> utils.PanedWindow:
    return _get_state().horizontal_panedwindow


def get_vertical_panedwindow() -> utils.PanedWindow:
    return _get_state().vertical_panedwindow


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
    for tab in get_tab_manager().tabs():
        if not tab.can_be_closed():
            return
        # the tabs must not be closed here, otherwise some of them
        # are closed if not all tabs can be closed
    get_main_window().event_generate("<<PorcupineQuit>>")  # TODO: still needed?
    for tab in get_tab_manager().tabs():
        get_tab_manager().close_tab(tab)
    get_main_window().destroy()
