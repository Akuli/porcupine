import tkinter as tk

from porcupine import tabs
from porcupine import __version__ as _porcupine_version

# i have experimented with a logging handler that displays logging
# messages in the label, but it's not as good idea as it sounds like,
# not all INFO messages are something that users should see all the time


class StatusBar(tk.Frame):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._active_tab = None

        self._file_label = tk.Label(self)
        self._file_label.pack(side='left')
        self._cursor_label = tk.Label(self)
        self._cursor_label.pack(side='right')

    def tab_callback(self, tab):
        if not isinstance(tab, tabs.FileTab):
            # ignore other kinds of tabs for now
            tab = None
        self._active_tab = tab

        if tab is not None:
            tab.path_changed_hook.connect(self.do_update)
            tab.textwidget.cursor_move_hook.connect(self.do_update)

        self.do_update()
        yield

        if tab is not None:
            tab.path_changed_hook.disconnect(self.do_update)
            tab.textwidget.cursor_move_hook.disconnect(self.do_update)

    # this is do_update() because tkinter has a method called update()
    def do_update(self, *junk):
        if self._active_tab is None:
            self._file_label['text'] = "Welcome to Porcupine %s!" % _porcupine_version
            self._cursor_label['text'] = ""
            return

        file = self._active_tab.path
        if file is None:
            # use the text of the top label
            self._file_label['text'] = self._active_tab.label['text']
        else:
            self._file_label['text'] = "File '%s'" % file

        line, column = (self._active_tab.textwidget
                        .index('insert').split('.'))
        self._cursor_label['text'] = "Line %s, column %s" % (line, column)


def setup(editor):
    statusbar = StatusBar(editor, relief='sunken')
    editor.tab_changed_hook.connect(statusbar.tab_callback)
    statusbar.do_update()

    # TODO: convert the find/replace area into a plugin and make sure
    # that it's always above the statusbar?
    statusbar.pack(side='bottom', fill='x')
