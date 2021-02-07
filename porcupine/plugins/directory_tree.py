import logging
import os
import pathlib
import subprocess
import sys
import time
import tkinter
from functools import partial
from tkinter import ttk
from typing import Any, Dict, Iterator, List, Optional, Tuple

from porcupine import get_paned_window, get_tab_manager, settings, tabs, utils

log = logging.getLogger(__name__)

# If more than this many projects are opened, then the least recently opened
# project will be closed, unless a file has been opened from that project.
PROJECT_AUTOCLOSE_COUNT = 3


def run_git_status(project_root: pathlib.Path) -> Dict[pathlib.Path, str]:
    try:
        start = time.perf_counter()
        run_result = subprocess.run(
            ['git', 'status', '--ignored', '--porcelain'],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # for logging error message
            encoding=sys.getfilesystemencoding(),
        )
        log.debug(f"git ran in {round((time.perf_counter() - start)*1000)}ms")

        if run_result.returncode != 0:
            log.info(f"git failed: {run_result}")
            return {}

    except (OSError, UnicodeError):
        log.warning("can't run git", exc_info=True)
        return {}

    # Show .git as ignored, even though it actually isn't
    result = {project_root / '.git': 'git_ignored'}
    for line in run_result.stdout.splitlines():
        path = project_root / line[3:]
        if line[1] == 'M':
            result[path] = 'git_modified'
        elif line[1] == ' ':
            result[path] = 'git_added'
        elif line[:2] == '??':
            result[path] = 'git_untracked'
        elif line[:2] == '!!':
            result[path] = 'git_ignored'
        else:
            log.warning(f"unknown git status line: {repr(line)}")
    return result


class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse', show='tree')
        self.bind('<Double-Button-1>', self.on_click, add=True)
        self.bind('<<TreeviewOpen>>', self.on_click, add=True)
        self.bind('<<ThemeChanged>>', self._config_tags, add=True)
        self._config_tags()
        self.git_statuses: Dict[pathlib.Path, Dict[pathlib.Path, str]] = {}

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

        # Add project to beginning so it won't be hidden soon
        project_item_id = self.insert('', 0, text=text, values=[root_path], tags=['dir', 'project'], open=False)
        self._insert_dummy(project_item_id)
        self.hide_old_projects()
        self.refresh_everything()

    def hide_old_projects(self, junk: object = None) -> None:
        for project_id in reversed(self.get_children('')):
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

        # Settings is a weird place for this, but easier than e.g. using a cache file.
        settings.set('directory_tree_projects', [str(self.get_path(id)) for id in self.get_children()])

    def open_and_refresh_directory(self, dir_path: Optional[pathlib.Path], dir_id: str) -> None:
        if self._contains_dummy(dir_id):
            self.delete(self.get_children(dir_id)[0])

        path2id = {self.get_path(id): id for id in self.get_children(dir_id)}
        if dir_path is None:
            # refreshing an entire project
            assert not dir_id
            new_paths = set(path2id.keys())
        else:
            new_paths = set(dir_path.iterdir())
            if not new_paths:
                self._insert_dummy(dir_id)
                return

        # TODO: handle changing directory to file
        for path in (path2id.keys() - new_paths):
            self.delete(path2id[path])
        for path in list(new_paths - path2id.keys()):
            tag = 'dir' if path.is_dir() else 'file'
            path2id[path] = self.insert(dir_id, 'end', text=path.name, values=[path], tags=tag, open=False)
            if path.is_dir():
                assert dir_path is not None
                self._insert_dummy(path2id[path])

        project_roots = set(map(self.get_path, self.get_children()))

        for child_path, child_id in path2id.items():
            relevant_parents = [child_path]
            parent_iterator = iter(child_path.parents)
            while relevant_parents[-1] not in project_roots:
                relevant_parents.append(next(parent_iterator))
            git_status = self.git_statuses[relevant_parents[-1]]

            old_tags = set(self.item(child_id, 'tags'))
            new_tags = {tag for tag in old_tags if not tag.startswith('git_')}

            for path in relevant_parents:
                if path in git_status:
                    new_tags.add(git_status[path])
                    break
            else:
                # Handle directories containing files with different statuses
                child_tags = {
                    status
                    for subpath, status in git_status.items()
                    if status in {'git_added', 'git_modified'}
                    and str(subpath).startswith(str(child_path))  # optimization
                    and child_path in subpath.parents
                }
                if child_tags == {'git_added', 'git_modified'}:
                    new_tags.add('git_modified')
                else:
                    assert len(child_tags) <= 1
                    new_tags |= child_tags

            if old_tags != new_tags:
                self.item(child_id, tags=list(new_tags))

            if 'dir' in new_tags and not self._contains_dummy(child_id):
                self.open_and_refresh_directory(child_path, child_id)

        if dir_path is not None:
            assert set(self.get_children(dir_id)) == set(path2id.values())
            for index, (path, child_id) in enumerate(sorted(path2id.items(), key=self._sorting_key)):
                self.move(child_id, dir_id, index)

    def _sorting_key(self, path_id_pair: Tuple[pathlib.Path, str]) -> Tuple[Any, ...]:
        path, item_id = path_id_pair
        tags = self.item(item_id, 'tags')

        git_tags = [tag for tag in tags if tag.startswith('git_')]
        assert len(git_tags) < 2
        git_tag = git_tags[0] if git_tags else None

        return (
            1 if 'dir' in tags else 2,
            ['git_added', 'git_modified', None, 'git_untracked', 'git_ignored'].index(git_tag),
            str(path),
        )

    def refresh_everything(self, junk: object = None) -> None:
        log.debug("refreshing begins")
        start = time.perf_counter()

        self.hide_old_projects()
        self.git_statuses = {
            path: run_git_status(path)
            for path in map(self.get_path, self.get_children())
        }
        self.open_and_refresh_directory(None, '')

        log.debug(f"refreshed in {round((time.perf_counter() - start)*1000)}ms")

    def _insert_dummy(self, parent: str) -> None:
        assert parent
        self.insert(parent, 'end', text='(empty)', tags='dummy')

    def _contains_dummy(self, parent: str) -> bool:
        children = self.get_children(parent)
        return (len(children) == 1 and 'dummy' in self.item(children[0], 'tags'))

    def on_click(self, event: tkinter.Event) -> None:
        try:
            [selected_id] = self.selection()
        except ValueError:
            # nothing selected, can happen when double-clicking something else than one of the items
            return

        tags = self.item(selected_id, 'tags')
        if 'dir' in tags:
            self.open_and_refresh_directory(self.get_path(selected_id), selected_id)
        elif 'file' in tags:
            get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), self.get_path(selected_id)))

    def get_path(self, item_id: str) -> pathlib.Path:
        assert 'dummy' not in self.item(item_id, 'tags')
        return pathlib.Path(self.item(item_id, 'values')[0])

    def _get_children_recursively(self, item_id: str) -> Iterator[str]:
        for child in self.get_children(item_id):
            yield child
            yield from self._get_children_recursively(child)


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

        tab.bind('<<Save>>', tree.refresh_everything, add=True)
        tab.textwidget.bind('<FocusIn>', tree.refresh_everything, add=True)


def setup() -> None:
    # TODO: add something for finding a file by typing its name?
    container = ttk.Frame(get_paned_window())
    tree = DirectoryTree(container)
    tree.pack(side='left', fill='both', expand=True)
    tree.bind('<FocusIn>', tree.refresh_everything, add=True)
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
