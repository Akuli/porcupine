import tkinter as tk

from porcupine import plugins
from porcupine.settings import config


class StatusBar(tk.Label):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._active_tab = None

    def set_active_tab(self, tab):
        if self._active_tab is not None:
            self._active_tab.textwidget.cursor_move_hook.disconnect(self.update)
        if tab is not None:
            tab.textwidget.cursor_move_hook.connect(self.update)
        self._active_tab = tab
        self.update()

    def update(self, *junk):
        if self._active_tab is None:
            self['text'] = "Welcome to Porcupine!"
        else:
            textwidget = self._active_tab.textwidget
            line, column = textwidget.index('insert').split('.')
            self['text'] = "Line %s, column %s" % (line, column)


def session_hook(editor):
    statusbar = StatusBar(editor, anchor='w', relief='sunken')
    editor.tabmanager.tab_changed_hook.connect(statusbar.set_active_tab)

    # TODO: display logging messages in the statusbar
    statusbar.update(None, None)

    def set_enabled(junk):
        enabled = config['GUI'].getboolean('statusbar', True)
        # TODO: convert the find/replace area into a plugin that goes
        # into the editor, but to make sure that it's always above the
        # statusbar?
        if enabled:
            statusbar.pack(side='bottom', fill='x')
        else:
            statusbar.pack_forget()

    with config.connect('GUI', 'statusbar', set_enabled):
        yield


plugins.add_plugin("Statusbar", session_hook=session_hook)
