import tkinter as tk

import porcupine
from porcupine import tabs

# i have experimented with a logging handler that displays logging
# messages in the label, but it's not as good idea as it sounds like,
# not all INFO messages are something that users should see all the time


# this widget is kind of weird
class LabelWithEmptySpaceAtLeft(tk.Label):

    def __init__(self, master):
        self._spacer = tk.Frame(master)
        self._spacer.pack(side='left', expand=True)
        super().__init__(master)
        self.pack(side='left')

    def destroy(self):
        self._spacer.destroy()
        super().destroy()


class StatusBar(tk.Frame):

    def __init__(self, parent, tabmanager, **kwargs):
        super().__init__(parent, **kwargs)

        self._tab_manager = tabmanager
        tabmanager.bind('<<NewTab>>', self.on_new_tab, add=True)
        tabmanager.bind('<<CurrentTabChanged>>', self.do_update, add=True)
        self._current_tab = None

        # each label for each tab-separated thing
        self.labels = [tk.Label(self)]
        self.labels[0].pack(side='left')

    def set_text(self, tab_separated_text):
        parts = tab_separated_text.split('\t')
        while len(self.labels) > len(parts):
            # there's always at least one part, the label added in
            # __init__ is not destroyed here
            self.labels.pop().destroy()
        while len(self.labels) < len(parts):
            self.labels.append(LabelWithEmptySpaceAtLeft(self))

        for label, text in zip(self.labels, parts):
            label['text'] = text

    # this is do_update() because tkinter has a method called update()
    def do_update(self, junk=None):
        if self._tab_manager._current_tab is None:
            self.set_text("Welcome to Porcupine %s!" % porcupine.__version__)
        else:
            self.set_text(self._tab_manager._current_tab.status)

    def on_new_tab(self, event):
        event.widget.tabs[-1].bind('<<StatusChanged>>', self.do_update)
        # <<CurrentTabChanged>> will take care of calling do_update()


def setup():
    # TODO: add a frame to the main window for plugins to add stuff like
    # this?
    statusbar = StatusBar(porcupine.get_main_window(),
                          porcupine.get_tab_manager(), relief='sunken')
    statusbar.pack(side='bottom', fill='x')
    statusbar.do_update()

    tabmanager = porcupine.get_tab_manager()
    tabmanager.bind('<<NewTab>>', statusbar.on_new_tab, add=True)
