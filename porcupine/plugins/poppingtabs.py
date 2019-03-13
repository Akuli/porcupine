"""Dragging tabs out of a Porcupine window."""

import logging
import os
import pickle
import subprocess
import sys
import tempfile
import threading

import teek as tk

import porcupine
from porcupine import pluginloader, settings

log = logging.getLogger(__name__)


POPUP_SIZE = (600, 400)

# special state markers
NO_TABS = object()
NOT_POPPABLE = object()
NOT_DRAGGING = object()
SPECIAL_STATES = {NO_TABS, NOT_POPPABLE, NOT_DRAGGING}


def _is_on_window(event):
    window = event.widget.winfo_toplevel()
    # TODO: add winfo_x and winfo_y to pythotk
    window_left = tk.tcl_call(int, 'winfo', 'x', window)
    window_top = tk.tcl_call(int, 'winfo', 'y', window)
    window_right = window_left + window.winfo_width()
    window_bottom = window_top + window.winfo_height()

    return ((window_left < event.rootx < window_right) and
            (window_top < event.rooty < window_bottom))


# TODO: tests?
def _2lines(string):
    # convert a space in the middle into a newline
    words = string.split()
    center = len(words) // 2
    return ' '.join(words[:center]) + '\n' + ' '.join(words[center:])


class PopManager:

    def __init__(self):
        self._window = tk.Toplevel()
        self._window.withdraw()

        # TODO: add overrideredirect to pythotk
        tk.tcl_call(None, 'wm', 'overrideredirect', self._window, True)

        # the label is not ttk because i want it to look yellowish
        self._label_path = self._window.to_tcl() + '.label'
        tk.tcl_call(None, 'label', self._label_path,
                    '-fg', '#000', '-bg', '#ffc')
        tk.tcl_call(None, 'pack', self._label_path)

        self._dragged_state = NOT_DRAGGING

    def _show_tooltip(self, event):
        if self._window.wm_state == 'withdrawn':
            self._window.deiconify()

        width = tk.tcl_call(int, 'winfo', 'reqwidth', self._label_path)
        height = tk.tcl_call(int, 'winfo', 'reqheight', self._label_path)
        self._window.geometry(
            x=(event.rootx - (width // 2)),     # centered
            y=(event.rooty - height))           # above cursor

    # no need to return 'break' imo, other plugins are free to follow
    # drags and drops
    def on_drag(self, event):
        if _is_on_window(event):
            self._window.withdraw()
            return

        if self._dragged_state is NOT_DRAGGING:
            tab = porcupine.get_tab_manager().selected_tab
            if tab is None:
                # no tabs to pop up
                self._dragged_state = NO_TABS
                self._window.withdraw()
                return

            state = tab.get_state()
            if state is None:
                self._dragged_state = NOT_POPPABLE
                tk.tcl_call(None, self._label_path, 'configure', '-text',
                            _2lines("This tab cannot be popped up."))
            else:
                self._dragged_state = (tab, state)
                tk.tcl_call(None, self._label_path, 'configure', '-text',
                            _2lines("Drop the tab here to pop it up..."))

        self._show_tooltip(event)

    def on_drop(self, event):
        self._window.withdraw()
        if not (_is_on_window(event) or
                self._dragged_state in SPECIAL_STATES):
            log.info("popping off a tab")
            plugin_names = pluginloader.get_loaded_plugins()
            for bad_plugin in ['restart', 'geometry']:
                # these plugins are not suitable for popups
                if bad_plugin in plugin_names:
                    plugin_names.remove(bad_plugin)

            tab, state = self._dragged_state

            # TODO: add winfo_reqwidth and winfo_reqheight to pythotk
            reqwidth = tk.tcl_call(int, 'winfo', 'reqwidth', tab.content)
            reqheight = tk.tcl_call(int, 'winfo', 'reqheight', tab.content)

            message = (type(tab), state, plugin_names, (reqwidth, reqheight),
                       porcupine.get_init_kwargs(), event.rootx, event.rooty)
            with tempfile.NamedTemporaryFile(delete=False) as file:
                log.debug("writing dumped state to '%s'", file)
                pickle.dump(message, file)

            settings.save()     # let the new process use up-to-date settings
            process = subprocess.Popen([sys.executable, '-m', __name__,
                                        file.name])
            log.debug("started subprocess with PID %d", process.pid)

            # TODO: should the subprocess send some kind of 'deleted' message
            #       to this process, and then this process wouldn't close the
            #       tab until it receives the message?
            tab.close()

            # don't exit python until the subprocess exits, also log stuff
            threading.Thread(target=self._waiter_thread,
                             args=[process]).start()

        self._dragged_state = NOT_DRAGGING

    def _waiter_thread(self, process):
        status = process.wait()
        if status == 0:
            log.debug("subprocess with PID %d exited successfully",
                      process.pid)
        else:
            log.warning("subprocess with PID %d exited with status %d",
                        process.pid, status)


def setup():
    manager = PopManager()
    porcupine.get_tab_manager().bind(
        '<Button1-Motion>', manager.on_drag, event=True)
    porcupine.get_tab_manager().bind(
        '<ButtonRelease-1>', manager.on_drop, event=True)


def _run_popped_up_process():
    prog, state_path = sys.argv
    with open(state_path, 'rb') as file:
        (tabtype, state, plugin_names, required_size, init_kwargs,
         mousex, mousey) = pickle.load(file)

    porcupine.init(**init_kwargs)

    # center the window around the mouse
    width, height = POPUP_SIZE
    reqwidth, reqheight = required_size
    reqheight += 50     # for stuff outside tabs

    top = mousey - height//2
    left = mousex - height//2
    porcupine.get_main_window().geometry(
        max(width, reqwidth), max(height, reqheight), left, top)

    pluginloader.load(plugin_names)
    tabmanager = porcupine.get_tab_manager()
    tabmanager.append_and_select(tabtype.from_state(tabmanager, state))

    # the state file is not removed earlier because if anything above
    # fails, it still exists and can be recovered like this:
    #
    #   $ python3 -m porcupine.plugins.poppingtabs /path/to/the/state/file
    #
    # most of the time this should "just work", so user-unfriendliness
    # is not a huge problem
    os.remove(state_path)
    porcupine.run()


if __name__ == '__main__':
    _run_popped_up_process()
