import tkinter as tk

from porcupine import plugins
from porcupine.settings import config


class StatusBar(tk.Label):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._active_tab = None

    def set_active_tab(self, tab):
        if self._active_tab is not None:
            self._active_tab.textwidget.on_cursor_move.remove(self.update)
        if tab is not None:
            tab.textwidget.on_cursor_move.append(self.update)
        self._active_tab = tab
        self.update()

    def update(self):
        if self._active_tab is None:
            self['text'] = "Welcome to Porcupine!"
        else:
            text = self._active_tab.textwidget
            line, column = text.index('insert').split('.')
            self['text'] = "Line %s, column %s" % (line, column)


def session_hook(editor):
    statusbar = StatusBar(editor, anchor='w', relief='sunken')
    editor.tabmanager.on_tab_changed.append(statusbar.set_active_tab)

    # TODO: display the Porcupine version in the status bar when it
    # starts? or maybe some messages about failing to load plugins?
    statusbar.update()

    @config.connect('gui:statusbar')
    def set_enabled(enabled):
        # TODO: convert the find/replace area into a plugin that goes
        # into the editor, but to make sure that it's always above the
        # statusbar?
        if enabled:
            statusbar.pack(side='bottom', fill='x')
        else:
            statusbar.pack_forget()

    with set_enabled:    # config.connect() returned a context manager
        yield


plugins.add_plugin("Statusbar", session_hook=session_hook)
