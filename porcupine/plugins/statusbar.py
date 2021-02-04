"""Display a status bar in each file tab."""
from tkinter import ttk

from porcupine import get_tab_manager, tabs


class StatusBar(ttk.Frame):

    def __init__(self, tab: tabs.FileTab):
        super().__init__(tab.bottom_frame)
        self.tab = tab
        self.left_label = ttk.Label(self)
        self.right_label = ttk.Label(self)
        self.left_label.pack(side='left')
        self.right_label.pack(side='right')

    def on_path_changed(self, junk: object = None) -> None:
        self.left_label.config(text=("New file" if self.tab.path is None else str(self.tab.path)))

    def on_cursor_moved(self, junk: object = None) -> None:
        line, column = self.tab.textwidget.index('insert').split('.')
        self.right_label.config(text=f"Line {line}, column {column}")


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        statusbar = StatusBar(tab)
        statusbar.pack(side='bottom', fill='x')
        tab.bind('<<PathChanged>>', statusbar.on_path_changed, add=True)
        tab.textwidget.bind('<<CursorMoved>>', statusbar.on_cursor_moved, add=True)

        statusbar.on_path_changed()
        statusbar.on_cursor_moved()


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
