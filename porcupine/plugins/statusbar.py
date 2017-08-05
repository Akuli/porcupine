import tkinter as tk

import porcupine
from porcupine import tabs

# i have experimented with a logging handler that displays logging
# messages in the label, but it's not as good idea as it sounds like,
# not all INFO messages are something that users should see all the time


class StatusBar(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._current_tab = None

        self._file_label = tk.Label(self)
        self._file_label.pack(side='left')
        self._cursor_label = tk.Label(self)
        self._cursor_label.pack(side='right')

    def on_new_tab(self, event):
        tab = event.widget.tabs[-1]

        # do_update() can get called more often than necessary, but it
        # doesn't matter
        tab.path_changed_hook.connect(self.do_update)
        tab.filetype_changed_hook.connect(self.do_update)
        tab.textwidget.bind('<<CursorMoved>>', self.do_update, add=True)

    def on_tab_changed(self, event):
        if event.widget.tabs:
            self._current_tab = event.widget.tabs[-1]
        else:
            self._current_tab = None
        self.do_update()

    # this is do_update() because tkinter has a method called update()
    def do_update(self, *junk):
        if self._current_tab is None:
            self._file_label['text'] = ("Welcome to Porcupine %s!"
                                        % porcupine.__version__)
            self._cursor_label['text'] = ""
            return

        if (isinstance(self._current_tab, tabs.FileTab) and
                self._current_tab.path is not None):
            self._file_label['text'] = "File '%s'" % self._current_tab.path
        else:
            # the top label's text is usually "New File"
            self._file_label['text'] = self._current_tab.label['text']

        if isinstance(self._current_tab, tabs.FileTab):
            # TODO: add a drop-down (or up?) menu for choosing the filetype
            self._file_label['text'] += ", " + self._current_tab.filetype.name
            cursor = self._current_tab.textwidget.index('insert').split('.')
            self._cursor_label['text'] = "Line %s, column %s" % tuple(cursor)
        else:
            self._cursor_label['text'] = ''


def setup():
    # TODO: add a frame to the main window for plugins to add stuff like
    # this?
    statusbar = StatusBar(porcupine.get_main_window(), relief='sunken')
    statusbar.pack(side='bottom', fill='x')
    statusbar.do_update()

    tabmanager = porcupine.get_tab_manager()
    tabmanager.bind('<<NewTab>>', statusbar.on_new_tab, add=True)
    tabmanager.bind('<<CurrentTabChanged>>', statusbar.on_tab_changed,
                    add=True)
