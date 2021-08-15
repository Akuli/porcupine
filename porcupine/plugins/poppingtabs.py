"""Allow dragging tabs out of the Porcupine window."""
from __future__ import annotations

import enum
import logging
import os
import pickle
import subprocess
import sys
import tempfile
import threading
import tkinter
from typing import Any

from porcupine import (
    get_main_window,
    get_parsed_args,
    get_tab_manager,
    menubar,
    pluginloader,
    settings,
    tabs,
)

log = logging.getLogger(__name__)


class DragState(enum.Enum):
    NO_TABS = enum.auto()
    NOT_POPPABLE = enum.auto()
    NOT_DRAGGING = enum.auto()


def is_on_window(event: tkinter.Event[tkinter.Misc]) -> bool:
    window = event.widget.winfo_toplevel()
    window_left = window.winfo_x()
    window_right = window_left + window.winfo_width()
    window_top = window.winfo_y()
    window_bottom = window_top + window.winfo_height()
    window_top -= 50  # menu bar and window border

    return (window_left < event.x_root < window_right) and (
        window_top < event.y_root < window_bottom
    )


class PopManager:
    def __init__(self) -> None:
        self._window = tkinter.Toplevel()
        self._window.withdraw()
        self._window.overrideredirect(True)

        # this is not ttk because i want it to look yellowish
        self._label = tkinter.Label(self._window, fg="#000", bg="#ffc")
        self._label.pack()

        self._dragged_state: DragState | tuple[tabs.Tab, Any] = DragState.NOT_DRAGGING

    def _show_tooltip(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if self._window.state() == "withdrawn":
            self._window.deiconify()

        left = event.x_root - (self._label.winfo_reqwidth() // 2)  # centered
        top = event.y_root - self._label.winfo_reqheight()  # above cursor
        self._window.geometry(f"+{left}+{top}")

    # no need to return 'break' imo, other plugins are free to follow
    # drags and drops
    def on_drag(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if is_on_window(event):
            self._window.withdraw()
            return

        if self._dragged_state == DragState.NOT_DRAGGING:
            tab = get_tab_manager().select()
            if tab is None:
                # no tabs to pop up
                self._dragged_state = DragState.NO_TABS
                self._window.withdraw()
                return

            state = tab.get_state()
            if state is None:
                self._dragged_state = DragState.NOT_POPPABLE
                self._label.config(text="This tab cannot\nbe popped up.")
            else:
                self._dragged_state = (tab, state)
                self._label.config(text="Drop the tab here\nto pop it up...")

        self._show_tooltip(event)

    def on_drop(self, event: tkinter.Event[tkinter.Misc]) -> None:
        self._window.withdraw()
        if not (is_on_window(event) or isinstance(self._dragged_state, DragState)):
            log.info("popping off a tab")
            tab, state = self._dragged_state

            # At least 600x400, bigger if necessary. Can't use
            # get_main_window.winfo_reqwidth because that's huge
            # when there's a lot of tabs.
            width = max(600, tab.winfo_reqwidth())
            height = max(400, get_main_window().winfo_reqheight())

            # Center the window
            x = event.x_root - round(width / 2)
            y = event.y_root - round(height / 2)

            # Make sure it's not off screen
            screen_width = get_main_window().winfo_screenwidth()
            screen_height = get_main_window().winfo_screenheight()
            width = min(width, screen_width)
            height = min(height, screen_height)
            x = min(x, screen_width - width)
            y = min(y, screen_height - height)
            x = max(0, x)
            y = max(0, y)
            self.pop(tab, state, f"{width}x{height}+{x}+{y}")

        self._dragged_state = DragState.NOT_DRAGGING

    def pop(self, tab: tabs.Tab, state: Any, geometry: str) -> None:
        log.info(f"Popping {repr(tab)} to {geometry} begins")
        message = (type(tab), state, geometry)
        with tempfile.NamedTemporaryFile(delete=False) as file:
            log.info(f"writing pickled state to {file.name}")
            pickle.dump(message, file)

        settings.save()  # let the new process use up-to-date settings

        # The subprocess must be called so that it has a sane sys.path.
        # In particular, import or don't import from current working
        # directory exactly like the porcupine that is currently running.
        # Importing from current working directory is bad if it contains
        # e.g. queue.py (#31), but good when that's where porcupine is
        # meant to be imported from (#230).
        code = f"import sys; sys.path[:] = {sys.path}; from porcupine.__main__ import main; main()"
        args = [sys.executable, "-c", code]  # FIXME: sys.executable.endswith(r"\Porcupine.exe")

        args.append("--without-plugins")
        args.append(
            ",".join(
                {
                    info.name
                    for info in pluginloader.plugin_infos
                    if info.status == pluginloader.Status.DISABLED_ON_COMMAND_LINE
                }
                | {
                    # these plugins are not suitable for popups
                    # TODO: geometry and restart stuff don't get saved
                    "restart",
                    "geometry",
                }
            )
        )

        if get_parsed_args().verbose_logger is not None:
            args.append("--verbose-logger")
            args.append(get_parsed_args().verbose_logger)

        process = subprocess.Popen(
            args, env={**os.environ, "PORCUPINE_POPPINGTABS_STATE_FILE": file.name}
        )
        log.debug(f"started subprocess with PID {process.pid}")
        get_tab_manager().close_tab(tab)

        # don't exit python until the subprocess exits, also log stuff
        threading.Thread(target=self._waiting_thread, args=[process]).start()

    def pop_next_to_current_window(self) -> None:
        tab = get_tab_manager().select()
        assert tab is not None
        state = tab.get_state()
        assert state is not None

        # Popup goes on the half of screen where the current main window is not
        window_center = get_main_window().winfo_rootx() + get_main_window().winfo_width() / 2
        half_screen_width = round(get_main_window().winfo_screenwidth() / 2)
        screen_height = get_main_window().winfo_screenheight()
        if window_center > half_screen_width:
            geometry = f"{half_screen_width}x{screen_height}+0+0"
        else:
            geometry = f"{half_screen_width}x{screen_height}+{half_screen_width}+0"
        self.pop(tab, state, geometry)

    def _waiting_thread(self, process: subprocess.Popen[bytes]) -> None:
        status = process.wait()
        if status == 0:
            log.debug(f"subprocess with PID {process.pid} exited successfully")
        else:
            log.warning(f"subprocess with PID {process.pid} exited with status {status}")


def open_tab_from_state_file() -> None:
    try:
        path = os.environ.pop("PORCUPINE_POPPINGTABS_STATE_FILE")
    except KeyError:
        return

    with open(path, "rb") as file:
        (tabtype, state, geometry) = pickle.load(file)
    get_main_window().geometry(geometry)
    get_tab_manager().add_tab(tabtype.from_state(get_tab_manager(), state))

    # the state file is not removed earlier because if anything above
    # fails, it still exists and can be recovered somehow
    #
    # most of the time this should "just work", so user-unfriendy recovery
    # is not a huge problem
    os.remove(path)


def setup() -> None:
    manager = PopManager()
    get_tab_manager().bind("<Button1-Motion>", manager.on_drag, add=True)
    get_tab_manager().bind("<ButtonRelease-1>", manager.on_drop, add=True)
    menubar.get_menu("View").add_command(
        label="Pop Tab", command=manager.pop_next_to_current_window
    )
    menubar.set_enabled_based_on_tab(
        "View/Pop Tab", (lambda tab: tab is not None and tab.get_state() is not None)
    )

    open_tab_from_state_file()
