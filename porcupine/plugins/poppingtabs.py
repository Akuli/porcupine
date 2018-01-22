"""Dragging tabs out of a Porcupine window."""

import os
import pickle
import subprocess
import sys
import tempfile
import tkinter

import porcupine
from porcupine import get_main_window, get_tab_manager, pluginloader


POPUP_SIZE = (600, 400)

# special state markers
NOT_DRAGGING = object()
NO_TABS = object()
NOT_POPPABLE = object()
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

    def on_drag(self, event):
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
            plugin_names = porcupine.pluginloader.get_loaded_plugins()

            # these plugins are not suitable for popups
            for bad_plugin in ['restart', 'geometry']:
                if bad_plugin in plugin_names:
                    plugin_names.remove(bad_plugin)

            tab, state = self._dragged_state
            message = (type(tab), state, plugin_names,
                       event.x_root, event.y_root)
            with tempfile.NamedTemporaryFile(delete=False) as file:
                pickle.dump(message, file)

            subprocess.Popen([sys.executable, '-m', __name__, file.name])
            get_tab_manager().close_tab(tab)

        self._dragged_state = NOT_DRAGGING


def setup():
    manager = PopManager()
    get_tab_manager().bind('<Button1-Motion>', manager.on_drag)
    get_tab_manager().bind('<ButtonRelease-1>', manager.on_drop)


def _run_popped_up_process():
    # TODO: what if this fails?? then the user may lose important stuff?
    prog, state_path = sys.argv
    with open(state_path, 'rb') as file:
        (tabtype, state, plugin_names, mousex, mousey) = pickle.load(file)

    porcupine.init()

    # center the window around the mouse
    width, height = POPUP_SIZE
    top = mousey - height//2
    left = mousex - height//2
    get_main_window().geometry('%dx%d+%d+%d' % (width, height, left, top))

    pluginloader.load(plugin_names)
    get_tab_manager().add_tab(tabtype.from_state(get_tab_manager(), state))
    os.remove(state_path)
    porcupine.run()


if __name__ == '__main__':
    _run_popped_up_process()
