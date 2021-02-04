"""Display a status bar in each file tab."""
import tkinter
from tkinter import ttk
from functools import partial

from porcupine import get_tab_manager, tabs


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

    def __init__(self, master: tkinter.BaseWidget):
        super().__init__(master)
        # one label for each tab-separated thing
        self.labels = [ttk.Label(self)]
        self.labels[0].pack(side='left')

    def set_status(self, status: str) -> None:
        parts = status.split('\t')

        # there's always at least one part, the label added in
        # __init__ is not destroyed here
        while len(self.labels) > len(parts):
            self.labels.pop().destroy()
        while len(self.labels) < len(parts):
            self.labels.append(LabelWithEmptySpaceAtLeft(self))

        for label, text in zip(self.labels, parts):
            label.config(text=text)


def update_status(tab: tabs.FileTab, statusbar: StatusBar, junk: object = None) -> None:
    if tab.path is None:
        path_string = "New file"
    else:
        path_string = str(tab.path)
    line, column = tab.textwidget.index('insert').split('.')
    statusbar.set_status(f"{path_string}\tLine {line}, column {column}")


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        statusbar = StatusBar(tab.bottom_frame)
        statusbar.pack(side='bottom', fill='x')
        tab.bind('<<PathChanged>>', partial(update_status, tab, statusbar), add=True)
        tab.textwidget.bind('<<CursorMoved>>', partial(update_status, tab, statusbar), add=True)
        update_status(tab, statusbar)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
