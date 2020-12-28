"""Display a status bar in each tab."""
import tkinter
from tkinter import ttk

from porcupine import get_tab_manager, tabs

# i have experimented with a logging handler that displays logging
# messages in the label, but it's not as good idea as it sounds like,
# not all INFO messages are something that users should see all the time


# this widget is kind of weird
class LabelWithEmptySpaceAtLeft(ttk.Label):

    def __init__(self, master: tkinter.BaseWidget) -> None:
        self._spacer = ttk.Frame(master)
        self._spacer.pack(side='left', expand=True)
        super().__init__(master)
        self.pack(side='left')

    def destroy(self) -> None:
        self._spacer.destroy()
        super().destroy()


class StatusBar(ttk.Frame):

    def __init__(self, master: tkinter.BaseWidget, tab: tabs.Tab):
        super().__init__(master)
        self.tab = tab
        # one label for each tab-separated thing
        self.labels = [ttk.Label(self)]
        self.labels[0].pack(side='left')

        tab.bind('<<StatusChanged>>', self.do_update, add=True)
        self.do_update()

    # this is do_update() because tkinter has a method called update()
    def do_update(self, junk: object = None) -> None:
        parts = self.tab.status.split('\t')

        # there's always at least one part, the label added in
        # __init__ is not destroyed here
        while len(self.labels) > len(parts):
            self.labels.pop().destroy()
        while len(self.labels) < len(parts):
            self.labels.append(LabelWithEmptySpaceAtLeft(self))

        for label, text in zip(self.labels, parts):
            label.config(text=text)


def on_new_tab(tab: tabs.Tab) -> None:
    StatusBar(tab.bottom_frame, tab).pack(side='bottom', fill='x')


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
