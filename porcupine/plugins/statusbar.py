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

    def show_path(self, junk: object = None) -> None:
        self.left_label.config(text=("New file" if self.tab.path is None else str(self.tab.path)))

    def show_cursor_pos(self, junk: object = None) -> None:
        line, column = self.tab.textwidget.index('insert').split('.')
        self.right_label.config(text=f"Line {line}, column {column}")

    def show_reload_warning(self, junk: object) -> None:
        self.left_label.config(
            foreground='red',
            text="File was reloaded. Press Ctrl+Z to get your changes back.",
        )

    def clear_reload_warning(self, junk: object) -> None:
        if self.left_label['foreground']:
            self.left_label.config(foreground='')
            self.show_path()


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        statusbar = StatusBar(tab)
        statusbar.pack(side='bottom', fill='x')
        tab.bind('<<PathChanged>>', statusbar.show_path, add=True)
        tab.bind('<<Reloaded>>', statusbar.show_reload_warning)
        tab.textwidget.bind('<<CursorMoved>>', statusbar.show_cursor_pos, add=True)
        tab.textwidget.bind('<<ContentChanged>>', statusbar.clear_reload_warning, add=True)

        statusbar.show_path()
        statusbar.show_cursor_pos()


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
