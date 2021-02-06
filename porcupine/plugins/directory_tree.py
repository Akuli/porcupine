import os
import pathlib
import tkinter
from tkinter import ttk
from functools import partial

from porcupine import get_paned_window, get_tab_manager, tabs, utils
from porcupine.plugins.langserver import find_project_root   # TODO: clean up


# TODO: handle files being deleted, copied, renamed, etc
class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse')
        self.bind('<<TreeviewOpen>>', self.on_click, add=True)
        self.bind('<<ThemeChanged>>', self._config_tags, add=True)
        self._config_tags()

    def add_project(self, root_path: pathlib.Path) -> None:
        for project_item_id in self.get_children():
            path = pathlib.Path(self.item(project_item_id, 'values')[0])
            if path == root_path or path in root_path.parents:
                # Project or parent project added already
                return
            if root_path in path.parents:
                # This project will replace the existing project
                self.delete(project_item_id)

        # TODO: show long paths more nicely
        if pathlib.Path.home() in root_path.parents:
            text = '~' + os.sep + str(root_path.relative_to(pathlib.Path.home()))
        else:
            text = str(root_path)

        project_item_id = self.insert('', 'end', text=text, values=[root_path], tags='project', open=False)
        self.process_directory(root_path, project_item_id)

    def _config_tags(self, junk: object = None) -> None:
        fg = self.tk.eval('ttk::style look Treeview -foreground')
        bg = self.tk.eval('ttk::style look Treeview -background')
        self.tag_configure('dummy', foreground=utils.mix_colors(fg, bg, 0.5))

    def process_directory(self, dir_path: pathlib.Path, parent_id: str) -> None:
        for child in self.get_children(parent_id):
            self.delete(child)

        paths = sorted(dir_path.iterdir())
        if paths:
            for path in paths:
                tag = 'dir' if path.is_dir() else 'file'
                n = self.insert(parent_id, 'end', text=path.name, values=[path], tags=tag, open=False)
                if path.is_dir():
                    self._insert_dummy(n)
        else:
            self._insert_dummy(parent_id)

    def on_click(self, event: tkinter.Event) -> None:
        [selection] = self.selection()
        tags = self.item(selection, 'tags')
        if 'file' in tags or 'dir' in tags:
            path = pathlib.Path(self.item(selection, 'values')[0])
            if 'dir' in tags:
                self.process_directory(path, selection)
            else:
                get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))

    def _insert_dummy(self, parent: str) -> None:
        self.insert(parent, 'end', text='(empty)', tags='dummy')


def on_new_tab(tree: DirectoryTree, tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        def callback(junk: object = None) -> None:
            assert isinstance(tab, tabs.FileTab)
            if tab.path is not None:
                tree.add_project(find_project_root(tab.path))

        callback()
        tab.bind('<<PathChanged>>', callback)


def setup() -> None:
    container = ttk.Frame(get_paned_window())
    tree = DirectoryTree(container)
    tree.pack(side='left', fill='both', expand=True)
    scrollbar = ttk.Scrollbar(container)
    scrollbar.pack(side='right', fill='y')

    tree.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    get_paned_window().insert(get_tab_manager(), container)   # insert before tab manager
    get_tab_manager().add_tab_callback(partial(on_new_tab, tree))
