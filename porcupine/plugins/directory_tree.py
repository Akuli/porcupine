import time
import logging
import os
import pathlib
import subprocess
import sys
import tkinter
from functools import partial
from tkinter import ttk
from typing import Dict, Iterator, List, Tuple, Any

from porcupine import get_paned_window, get_tab_manager, settings, tabs, utils

log = logging.getLogger(__name__)

# If more than this many projects are opened, then the least recently opened
# project will be closed, unless a file has been opened from that project.
PROJECT_AUTOCLOSE_COUNT = 3


# TODO: handle files being deleted, copied, renamed, etc
# TODO: remember projects when porcupine is closed
class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse', show='tree')
        self.bind('<Double-Button-1>', self.on_click, add=True)
        self.bind('<<TreeviewOpen>>', self.on_click, add=True)
        self.bind('<<ThemeChanged>>', self._config_tags, add=True)
        self._config_tags()

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
        self.tag_configure('git_untracked', foreground='red4')
        self.tag_configure('git_ignored', foreground=gray)

    def add_project(self, root_path: pathlib.Path) -> None:
        for project_item_id in self.get_children():
            path = self.get_path(project_item_id)
            if path == root_path or path in root_path.parents:
                # Project or parent project added already. Move it first to
                # avoid hiding it soon.
                self.move(project_item_id, '', 0)
                return
            if root_path in path.parents:
                # This project will replace the existing project
                self.delete(project_item_id)

        # TODO: show long paths more nicely
        if pathlib.Path.home() in root_path.parents:
            text = '~' + os.sep + str(root_path.relative_to(pathlib.Path.home()))
        else:
            text = str(root_path)

        project_item_id = self.insert('', 'end', text=text, values=[root_path], tags='dir', open=False)
        self._insert_dummy(project_item_id)
        self.hide_old_projects()
        self.save_project_list()

    def refresh_directory(self, dir_path: pathlib.Path, dir_id: str) -> None:
        for child in self.get_children(dir_id):
            self.delete(child)

        paths = dir_path.iterdir()
        if paths:
            for path in paths:
                tag = 'dir' if path.is_dir() else 'file'
                n = self.insert(dir_id, 'end', text=path.name, values=[path], tags=tag, open=False)
                if path.is_dir():
                    self._insert_dummy(n)
        else:
            self._insert_dummy(dir_id)

#        self.update_git_tags()

    def _insert_dummy(self, parent: str) -> None:
        self.insert(parent, 'end', text='(empty)', tags='dummy')

    def _contains_dummy(self, parent: str) -> None:
        children = self.get_children(parent)
        return (len(children) == 1 and 'dummy' in self.item(children[0], 'tags'))

    def hide_old_projects(self, junk: object = None) -> None:
        for project_id in self.get_children(''):
            project_path = self.get_path(project_id)

            if (
                not project_path.is_dir()
            ) or (
                len(self.get_children('')) > PROJECT_AUTOCLOSE_COUNT
                and not any(
                    isinstance(tab, tabs.FileTab)
                    and tab.path is not None
                    and project_path in tab.path.parents
                    for tab in get_tab_manager().tabs()
                )
            ):
                self.delete(project_id)

        self.save_project_list()

    def save_project_list(self):
        # Settings is a weird place for this, but easier than e.g. using a cache file.
        settings.set('directory_tree_projects', [str(self.get_path(id)) for id in self.get_children()])

    def on_click(self, event: tkinter.Event) -> None:
        [selected_id] = self.selection()
        tags = self.item(selected_id, 'tags')
        if 'file' in tags or 'dir' in tags:
            path = self.get_path(selected_id)
            if 'dir' in tags:
                self.refresh_directory(path, selected_id)
            else:
                get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))

    def get_path(self, item_id: str) -> pathlib.Path:
        return pathlib.Path(self.item(item_id, 'values')[0])

    def _get_children_recursively(self, item_id: str) -> Iterator[str]:
        for child in self.get_children(item_id):
            yield child
            yield from self._get_children_recursively(child)

    # FIXME: this runs too often, clicking text widget --> slow response
    def update_git_tags(self, junk: object = None) -> None:
        total_start = time.time()

        for project_id in self.get_children(''):
            project_path = self.get_path(project_id)

            start = time.time()
            try:
                run_result = subprocess.run(
                    ['git', 'status', '--ignored', '--porcelain'],
                    cwd=project_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding=sys.getfilesystemencoding(),
                )
                if run_result.returncode != 0:
                    log.info(f"git failed: {run_result}")
                    continue
            except (OSError, UnicodeError):
                log.warning("can't run git", exc_info=True)
                continue
            print(f"git ran for {round((time.time() - start)*1000)}ms")

            # Show .git as ignored, even though it actually isn't
            parsed_git_status = {project_path / '.git': 'git_ignored'}
            for line in run_result.stdout.splitlines():
                path = project_path / line[3:]
                if line[1] == 'M':
                    parsed_git_status[path] = 'git_modified'
                elif line[1] == ' ':
                    parsed_git_status[path] = 'git_added'
                elif line[:2] == '??':
                    parsed_git_status[path] = 'git_untracked'
                elif line[:2] == '!!':
                    parsed_git_status[path] = 'git_ignored'
                else:
                    log.warning(f"unknown git status line: {repr(line)}")

            self._update_git_tags_and_sort_dir(project_id, parsed_git_status)
            for item_id in self._get_children_recursively(project_id):
                if 'dir' in self.item(item_id, 'tags') and not self._contains_dummy(item_id):
                    self._update_git_tags_and_sort_dir(item_id, parsed_git_status)

        print(f"total time {round((time.time() - total_start)*1000)}ms")

    # TODO: use git tags when sorting
    def _update_git_tags_and_sort_dir(self, dir_id: str, parsed_git_status: Dict[pathlib.Path, str]) -> None:
        for child_id in self.get_children(dir_id):
            child_path = self.get_path(child_id)
            old_tags = set(self.item(child_id, 'tags'))
            new_tags = {tag for tag in old_tags if not tag.startswith('git_')}

            for status_path, tag in parsed_git_status.items():
                if status_path == child_path or status_path in child_path.parents:
                    new_tags.add(tag)
                    break
            else:
                # Handle directories containing files with different statuses
                new_tags |= {
                    status
                    for subpath, status in parsed_git_status.items()
                    if status in {'git_added', 'git_modified'}
                    and child_path in subpath.parents
                }

            if old_tags != new_tags:
                self.item(child_id, tags=list(new_tags))

        children = sorted(self.get_children(dir_id), key=self._sorting_key)
        for index, child_id in enumerate(children):
            self.move(child_id, dir_id, index)

    def _sorting_key(self, item_id) -> Tuple[Any, ...]:
        tags = self.item(item_id, 'tags')

        git_tags = [tag for tag in self.item(item_id, 'tags') if tag.startswith('git_')]
        assert len(git_tags) < 2
        git_tag = git_tags[0] if git_tags else None

        return (
            1 if 'dir' in tags else 2,
            ['git_added', 'git_modified', None, 'git_untracked', 'git_ignored'].index(git_tag),
            str(self.get_path(item_id)),
        )


def on_new_tab(tree: DirectoryTree, tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        def path_callback(junk: object = None) -> None:
            assert isinstance(tab, tabs.FileTab)
            if tab.path is not None:
                tree.add_project(utils.find_project_root(tab.path))

        path_callback()

        tab.bind('<<PathChanged>>', path_callback, add=True)
        tab.bind('<<PathChanged>>', tree.hide_old_projects, add=True)
        tab.bind('<Destroy>', tree.hide_old_projects, add=True)
#        tab.bind('<<Save>>', tree.update_git_tags, add=True)
#        tab.textwidget.bind('<FocusIn>', tree.update_git_tags, add=True)


def setup() -> None:
    # TODO: add something for finding a file by typing its name?
    container = ttk.Frame(get_paned_window())
    tree = DirectoryTree(container)
    tree.pack(side='left', fill='both', expand=True)
    scrollbar = ttk.Scrollbar(container)
    scrollbar.pack(side='right', fill='y')

    tree.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    get_paned_window().insert(get_tab_manager(), container)   # insert before tab manager
    get_tab_manager().add_tab_callback(partial(on_new_tab, tree))

    settings.add_option('directory_tree_projects', [], type=List[str])
    for path in [pathlib.Path(string) for string in settings.get('directory_tree_projects', List[str])]:
        if path.is_absolute() and path.is_dir() and utils.looks_like_project_root(path):
            tree.add_project(path)
