"""Allow dragging tabs out of the Porcupine window."""

import logging
import os
import pickle
import subprocess
import sys
import tempfile
import threading
import tkinter
from typing import Any, Tuple, Union

from porcupine import (get_main_window, get_parsed_args, get_tab_manager,
                       pluginloader, settings, tabs)

log = logging.getLogger(__name__)


class SpecialState:
    pass


NO_TABS = SpecialState()
NOT_POPPABLE = SpecialState()
NOT_DRAGGING = SpecialState()


def _is_on_window(event: 'tkinter.Event[tkinter.Misc]') -> bool:
    window = event.widget.winfo_toplevel()
    window_left = window.winfo_x()
    window_right = window_left + window.winfo_width()
    window_top = window.winfo_y()
    window_bottom = window_top + window.winfo_height()

    return ((window_left < event.x_root < window_right) and
            (window_top < event.y_root < window_bottom))


class PopManager:

    def __init__(self) -> None:
        self._window = tkinter.Toplevel()
        self._window.withdraw()
        self._window.overrideredirect(True)

        # this is not ttk because i want it to look yellowish
        self._label = tkinter.Label(self._window, fg='#000', bg='#ffc')
        self._label.pack()

        self._dragged_state: Union[SpecialState, Tuple[tabs.Tab, Any]] = NOT_DRAGGING

    def _show_tooltip(self, event: 'tkinter.Event[tkinter.Misc]') -> None:
        if self._window.state() == 'withdrawn':
            self._window.deiconify()

        left = event.x_root - (self._label.winfo_reqwidth() // 2)  # centered
        top = event.y_root - self._label.winfo_reqheight()      # above cursor
        self._window.geometry('+%d+%d' % (left, top))

    # no need to return 'break' imo, other plugins are free to follow
    # drags and drops
    def on_drag(self, event: 'tkinter.Event[tkinter.Misc]') -> None:
        if _is_on_window(event):
            self._window.withdraw()
            return

        if self._dragged_state is NOT_DRAGGING:
            tab = get_tab_manager().select()
            if tab is None:
                # no tabs to pop up
                self._dragged_state = NO_TABS
                self._window.withdraw()
                return

            state = tab.get_state()
            if state is None:
                self._dragged_state = NOT_POPPABLE
                self._label.config(text="This tab cannot\nbe popped up.")
            else:
                self._dragged_state = (tab, state)
                self._label.config(text="Drop the tab here\nto pop it up...")

        self._show_tooltip(event)

    def on_drop(self, event: 'tkinter.Event[tkinter.Misc]') -> None:
        self._window.withdraw()
        if not (_is_on_window(event) or isinstance(self._dragged_state, SpecialState)):
            log.info("popping off a tab")
            tab, state = self._dragged_state
            required_size = (tab.winfo_reqwidth(), tab.winfo_reqheight())
            message = (type(tab), state, required_size, event.x_root, event.y_root)

            with tempfile.NamedTemporaryFile(delete=False) as file:
                log.debug("writing dumped state to '%s'", file)
                pickle.dump(message, file)

            settings.save()     # let the new process use up-to-date settings

            # Empty string (aka "load from current working directory") becomes
            # the first item of sys.path when using -m, which isn't great if
            # your current working directory contains e.g. queue.py (issue 31).
            #
            # However, if the currently running porcupine imports from current
            # working directory (e.g. python3 -m porcupine), then the subprocess
            # should do that too.
            if os.getcwd() in sys.path:
                args = [sys.executable, '-m', 'porcupine']
            else:
                python_code = '''
import sys
if sys.path[0] == '':
    del sys.path[0]
from porcupine.__main__ import main
main()
'''
                args = [sys.executable, '-c', python_code]

            args.append('--without-plugins')
            args.append(','.join({
                info.name
                for info in pluginloader.plugin_infos
                if info.status == pluginloader.Status.DISABLED_ON_COMMAND_LINE
            } | {
                # these plugins are not suitable for popups
                # TODO: geometry and restart stuff don't get saved
                'restart',
                'geometry',
            }))

            if get_parsed_args().verbose:
                args.append('--verbose')

            process = subprocess.Popen(
                args,
                env={**os.environ, 'PORCUPINE_POPPINGTABS_STATE_FILE': file.name})
            log.debug("started subprocess with PID %d", process.pid)
            get_tab_manager().close_tab(tab)

            # don't exit python until the subprocess exits, also log stuff
            threading.Thread(target=self._waiter_thread,
                             args=[process]).start()

        self._dragged_state = NOT_DRAGGING

    def _waiter_thread(self, process: 'subprocess.Popen[bytes]') -> None:
        status = process.wait()
        if status == 0:
            log.debug("subprocess with PID %d exited successfully",
                      process.pid)
        else:
            log.warning("subprocess with PID %d exited with status %d",
                        process.pid, status)


def open_tab_from_state_file() -> None:
    try:
        path = os.environ.pop('PORCUPINE_POPPINGTABS_STATE_FILE')
    except KeyError:
        return

    with open(path, 'rb') as file:
        (tabtype, state, required_size, mousex, mousey) = pickle.load(file)

    # stupid default size
    width = 600
    height = 400

    reqwidth, reqheight = required_size
    reqheight += 50     # for stuff outside tabs

    # center the window around the mouse
    top = mousey - height//2
    left = mousex - height//2
    get_main_window().geometry('%dx%d+%d+%d' % (
        max(width, reqwidth), max(height, reqheight), left, top))

    get_tab_manager().add_tab(tabtype.from_state(get_tab_manager(), state))

    # the state file is not removed earlier because if anything above
    # fails, it still exists and can be recovered somehow
    #
    # most of the time this should "just work", so user-unfriendy recovery
    # is not a huge problem
    os.remove(path)


def setup() -> None:
    manager = PopManager()
    get_tab_manager().bind('<Button1-Motion>', manager.on_drag, add=True)
    get_tab_manager().bind('<ButtonRelease-1>', manager.on_drop, add=True)

    open_tab_from_state_file()
