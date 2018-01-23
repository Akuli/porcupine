"""Dragging tabs out of a Porcupine window."""

import os
import pickle
import subprocess
import sys
import tempfile
import threading
import tkinter

import porcupine
from porcupine import pluginloader, settings


POPUP_SIZE = (600, 400)

# special state markers
NO_TABS = object()
NOT_POPPABLE = object()
NOT_DRAGGING = object()
SPECIAL_STATES = {NO_TABS, NOT_POPPABLE, NOT_DRAGGING}


def _is_on_window(event):
    window = event.widget.winfo_toplevel()
    window_left = window.winfo_x()
    window_right = window_left + window.winfo_width()
    window_top = window.winfo_y()
    window_bottom = window_top + window.winfo_height()

    return ((window_left < event.x_root < window_right) and
            (window_top < event.y_root < window_bottom))


# TODO: add doctests or something?
def _2lines(string):
    # convert a space in the middle into a newline
    words = string.split()
    center = len(words) // 2
    return ' '.join(words[:center]) + '\n' + ' '.join(words[center:])


class PopManager:

    def __init__(self):
        self._window = tkinter.Toplevel()
        self._window.withdraw()
        self._window.overrideredirect(True)

        # this is not ttk because i want it to look yellowish
        self._label = tkinter.Label(self._window, fg='#000', bg='#ffc')
        self._label.pack()

        self._dragged_state = NOT_DRAGGING

    def _show_tooltip(self, event):
        if self._window.state() == 'withdrawn':
            self._window.deiconify()

        left = event.x_root - (self._label.winfo_reqwidth() // 2)  # centered
        top = event.y_root - self._label.winfo_reqheight()      # above cursor
        self._window.geometry('+%d+%d' % (left, top))

    # no need to return 'break' imo, other plugins are free to follow
    # drags and drops
    def on_drag(self, event):
        if _is_on_window(event):
            self._window.withdraw()
            return

        if self._dragged_state is NOT_DRAGGING:
            tab = porcupine.get_tab_manager().select()
            if tab is None:
                # no tabs to pop up
                self._dragged_state = NO_TABS
                self._window.withdraw()
                return

            state = tab.get_state()
            if state is None:
                self._dragged_state = NOT_POPPABLE
                self._label['text'] = _2lines(
                    "This tab cannot be popped up.")
            else:
                self._dragged_state = (tab, state)
                self._label['text'] = _2lines(
                    "Drop the tab here to pop it up...")

        self._show_tooltip(event)

    def on_drop(self, event):
        self._window.withdraw()
        if not (_is_on_window(event) or
                self._dragged_state in SPECIAL_STATES):
            # a valid state, let's pop it off :D
            plugin_names = pluginloader.get_loaded_plugins()

            # these plugins are not suitable for popups
            for bad_plugin in ['restart', 'geometry']:
                if bad_plugin in plugin_names:
                    plugin_names.remove(bad_plugin)

            tab, state = self._dragged_state
            message = (type(tab), state, plugin_names,
                       porcupine.get_init_kwargs(), event.x_root, event.y_root)
            with tempfile.NamedTemporaryFile(delete=False) as file:
                pickle.dump(message, file)

            settings.save()     # let the new process use up-to-date settings
            process = subprocess.Popen([sys.executable, '-m', __name__,
                                        file.name])
            porcupine.get_tab_manager().close_tab(tab)

            # don't exit python until the subprocess exits
            threading.Thread(target=process.wait).start()

        self._dragged_state = NOT_DRAGGING


def setup():
    manager = PopManager()
    porcupine.get_tab_manager().bind(
        '<Button1-Motion>', manager.on_drag, add=True)
    porcupine.get_tab_manager().bind(
        '<ButtonRelease-1>', manager.on_drop, add=True)


def _run_popped_up_process():
    prog, state_path = sys.argv
    with open(state_path, 'rb') as file:
        (tabtype, state, plugin_names, init_kwargs,
         mousex, mousey) = pickle.load(file)

    porcupine.init(**init_kwargs)

    # center the window around the mouse
    width, height = POPUP_SIZE
    top = mousey - height//2
    left = mousex - height//2
    porcupine.get_main_window().geometry(
        '%dx%d+%d+%d' % (width, height, left, top))

    pluginloader.load(plugin_names)
    tabmanager = porcupine.get_tab_manager()
    tabmanager.add_tab(tabtype.from_state(tabmanager, state))

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
