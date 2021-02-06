import logging
import subprocess
import os
import pathlib
import tkinter
from tkinter import ttk
from functools import partial
from typing import Iterator

from porcupine import get_paned_window, get_tab_manager, tabs, utils
from porcupine.plugins.langserver import find_project_root   # TODO: clean up


log = logging.getLogger(__name__)


# TODO: handle files being deleted, copied, renamed, etc
class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse', show='tree')
        self.bind('<Double-Button-1>', self.on_click, add=True)
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
        gray = utils.mix_colors(fg, bg, 0.5)

        if sum(self.winfo_rgb(fg)) > 3*0x7fff:
            # bright foreground color
            green = '#00ff00'
            red = '#ff0000'
        else:
            green = '#007f00'
            red = '#7f0000'

        self.tag_configure('dummy', foreground=gray)
        self.tag_configure('git_modified', foreground=red)
        self.tag_configure('git_added', foreground=green)
        self.tag_configure('git_untracked', foreground=red)
        self.tag_configure('git_ignored', foreground=gray)

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

        self.update_git_tags()

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

    def _get_path(self, item_id: str) -> pathlib.Path:
        return pathlib.Path(self.item(item_id, 'values')[0])

    def _get_children_recursively(self, item_id: str) -> Iterator[str]:
        for child in self.get_children(item_id):
            yield child
            yield from self._get_children_recursively(child)

    # TODO: use git tags when sorting
    def update_git_tags(self, junk: object = None) -> None:
        for project_id in self.get_children(''):
            project_path = self._get_path(project_id)

            try:
                git_status = subprocess.check_output(
                    ['git', 'status', '--ignored', '--porcelain'], cwd=project_path
                ).decode('utf-8')
            except (OSError, UnicodeError):
                log.info("can't run git", exc_info=True)
                git_status = ''

            # Show .git as ignored, even though it actually isn't
            parsed_git_status = {project_path / '.git': 'git_ignored'}
            for line in git_status.splitlines():
                path = project_path / line[3:]
                if line[1] == 'M':
                    tag = 'git_modified'
                elif line[1] == ' ':
                    tag = 'git_added'
                elif line[:2] == '??':
                    tag = 'git_untracked'
                elif line[:2] == '!!':
                    tag = 'git_ignored'
                else:
                    continue
                parsed_git_status[path] = tag

            for item_id in self._get_children_recursively(project_id):
                old_tags = set(self.item(item_id, 'tags'))
                if 'dummy' in old_tags:
                    continue

                item_path = self._get_path(item_id)
                new_tags = {tag for tag in old_tags if not tag.startswith('git_')}

                for path, tag in parsed_git_status.items():
                    if path == item_path or path in item_path.parents:
                        new_tags.add(tag)
                        break

                if old_tags != new_tags:
                    self.item(item_id, tags=list(new_tags))


def on_new_tab(tree: DirectoryTree, tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        def path_callback(junk: object = None) -> None:
            assert isinstance(tab, tabs.FileTab)
            if tab.path is not None:
                tree.add_project(find_project_root(tab.path))
            tree.update_git_tags()

        path_callback()

        tab.bind('<<PathChanged>>', path_callback, add=True)
        tab.bind('<<Save>>', tree.update_git_tags, add=True)
        tab.textwidget.bind('<<AutoReload>>', tree.update_git_tags, add=True)


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
