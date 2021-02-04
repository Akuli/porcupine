import tkinter as tk
import tkinter.ttk as ttk
import pathlib
from typing import List

from porcupine import get_paned_window, get_tab_manager, tabs
from porcupine.plugins.langserver import find_project_root


class Sidebar(ttk.Treeview):

    def __init__(self, master: tk.BaseWidget) -> None:
        super().__init__(master)
        self.path = pathlib.Path('.').resolve()
        self.nodes = {}
        self.populate()
        self.bind('<<TreeviewSelect>>', self.on_click)

    def populate(self) -> None:
        files: List[pathlib.Path] = []
        directories: List[pathlib.Path] = []

        for p in sorted(self.path.iterdir()):
            directories.append(p) if p.is_dir() else files.append(p)
        
        for d in directories:
            node = self.insert('', 'end', text=d.name, open=False)
            self.nodes[node] = d
            self._insert_dummy(node)
    
        for f in files:
            node = self.insert('', 'end', text=f.name, open=False)
            self.nodes[node] = f

    def process_directory(self, node: str) -> None:
        for child in self.get_children(node):
            self.delete(child)

        for path in self.nodes[node].iterdir():
            n = self.insert(node, 'end', text=path.name, open=False)
            self.nodes[n] = path
            if path.is_dir():
                self.process_directory(n)

    def on_click(self, event: tk.Event) -> None:
        selection = self.selection()[0]
        path = self.nodes[selection]
        if path.is_dir():
            self.process_directory(selection)
        else:
            get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))

    def _insert_dummy(self, node: str) -> None:
        self.insert(node, 'end', text='')


def setup() -> None:
    sidebar = Sidebar(get_paned_window())
    get_paned_window().insert(get_tab_manager(), sidebar)