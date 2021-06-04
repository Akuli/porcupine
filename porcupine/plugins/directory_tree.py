from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import sys
import time
import tkinter
from functools import partial
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from porcupine import get_main_window, get_paned_window, get_tab_manager, menubar, settings, tabs, utils

log = logging.getLogger(__name__)

# If more than this many projects are opened, then the least recently opened
# project will be closed, unless a file has been opened from that project.
PROJECT_AUTOCLOSE_COUNT = 10


def run_git_status(project_root: pathlib.Path) -> Dict[pathlib.Path, str]:
    try:
        start = time.perf_counter()
        run_result = subprocess.run(
            ['git', 'status', '--ignored', '--porcelain'],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # for logging error message
            encoding=sys.getfilesystemencoding(),
            **utils.subprocess_kwargs)
        log.debug(f"git ran in {round((time.perf_counter() - start)*1000)}ms")

        if run_result.returncode != 0:
            # likely not a git repo because missing ".git" dir
            log.info(f"git failed in {project_root}: {run_result}")
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
        elif line[:2] in {'AA', 'UU'}:
            result[path] = 'git_mergeconflict'
        else:
            log.warning(f"unknown git status line: {repr(line)}")
    return result


class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse', show='tree', style='DirectoryTree.Treeview')

        # Needs after_idle because selection hasn't updated when binding runs
        self.bind('<Button-1>', (lambda event: self.after_idle(self.on_click, event)), add=True)

        self.bind('<<TreeviewOpen>>', self.open_file_or_dir, add=True)
        self.bind('<<TreeviewSelect>>', self.update_selection_color, add=True)
        self.bind('<<ThemeChanged>>', self._config_tags, add=True)
        self.column('#0', minwidth=500)   # allow scrolling sideways
        self._config_tags()
        self.git_statuses: Dict[pathlib.Path, Dict[pathlib.Path, str]] = {}

        self._last_click_time = 0
        self._last_click_selection: Optional[Tuple[str, ...]] = None

    def on_click(self, event: tkinter.Event[DirectoryTree]) -> None:
        # Don't know why the usual double-click handling doesn't work. It
        # didn't work at all when update_selection_color was bound to
        # <<TreeviewSelect>>, but even without that, it was a bit fragile and
        # only worked sometimes.
        #
        # To find time between the two clicks of double-click, I made a program
        # that printed times when I clicked.
        selection = self.selection()
        if event.time - self._last_click_time < 500 and self._last_click_selection == selection:
            # double click
            self.open_file_or_dir()

        self._last_click_time = event.time
        self._last_click_selection = selection

    def _config_tags(self, junk: object = None) -> None:
        fg = self.tk.eval('ttk::style lookup Treeview -foreground')
        bg = self.tk.eval('ttk::style lookup Treeview -background')
        gray = utils.mix_colors(fg, bg, 0.5)

        if sum(self.winfo_rgb(fg)) > 3*0x7fff:
            # bright foreground color
            green = '#00ff00'
            orange = '#ff6e00'
        else:
            green = '#007f00'
            orange = '#e66300'

        self.tag_configure('dummy', foreground=gray)
        self.tag_configure('git_mergeconflict', foreground=orange)
        self.tag_configure('git_modified', foreground='red')
        self.tag_configure('git_added', foreground=green)
        self.tag_configure('git_untracked', foreground='red4')
        self.tag_configure('git_ignored', foreground=gray)

    def update_selection_color(self, event: object = None) -> None:
        try:
            [selected_id] = self.selection()
        except ValueError:   # nothing selected
            git_tags = []
        else:
            git_tags = [tag for tag in self.item(selected_id, 'tags') if tag.startswith('git_')]

        if git_tags:
            [tag] = git_tags
            color = self.tag_configure(tag, 'foreground')
            self.tk.call('ttk::style', 'map', 'DirectoryTree.Treeview', '-foreground', ['selected', color])
        else:
            # use default colors
            self.tk.eval('ttk::style map DirectoryTree.Treeview -foreground {}')

    # This allows projects to be nested. Here's why that's a good thing:
    # Consider two projects, blah/blah/outer and blah/blah/outer/blah/inner.
    # If the inner project is not shown when outer project is already in the
    # directory tree, and home folder somehow becomes a project (e.g. when
    # editing ~/blah.py), then the directory tree will present everything
    # inside the home folder as one project.
    def add_project(self, root_path: pathlib.Path, *, refresh: bool = True) -> None:
        for project_item_id in self.get_children():
            if self.get_path(project_item_id) == root_path:
                # Move project first to avoid hiding it soon
                self.move(project_item_id, '', 0)
                return

        # TODO: show long paths more nicely
        if pathlib.Path.home() in root_path.parents:
            text = '~' + os.sep + str(root_path.relative_to(pathlib.Path.home()))
        else:
            text = str(root_path)

        # Add project to beginning so it won't be hidden soon
        project_item_id = self.insert('', 0, text=text, values=[root_path], tags=['dir', 'project'], open=False)
        self._insert_dummy(project_item_id)
        self.hide_old_projects()
        if refresh:
            self.refresh_everything()

    def select_file(self, path: pathlib.Path) -> None:
        project_root = utils.find_project_root(path)

        matching_project_ids = [child for child in self.get_children() if self.get_path(child) == project_root]
        if not matching_project_ids:
            # Happens when tab changes because a file was just opened. This
            # will be called soon once the project has been added.
            log.info(f"can't select '{path}' because its project '{project_root}' was not found")
            return

        [id] = matching_project_ids
        for part in path.relative_to(project_root).parts:
            if self.item(id, 'open'):
                [id] = [child for child in self.get_children(id) if self.get_path(child).name == part]
            else:
                break

        self.selection_set(id)
        self.focus(id)
        self.see(id)

    def _insert_dummy(self, parent: str) -> None:
        assert parent
        self.insert(parent, 'end', text='(empty)', tags='dummy')

    def _contains_dummy(self, parent: str) -> bool:
        children = self.get_children(parent)
        return (len(children) == 1 and self.tag_has('dummy', children[0]))

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
        settings.set_('directory_tree_projects', [str(self.get_path(id)) for id in self.get_children()])

    def refresh_everything(self, junk: object = None, *, when_done: Callable[[], None] = (lambda: None)) -> None:
        log.debug("refreshing begins")
        self.hide_old_projects()

        # This must not be an iterator, otherwise thread calls self.get_path which does tkinter stuff
        paths = {child_id: self.get_path(child_id) for child_id in self.get_children()}

        def thread_target() -> Dict[pathlib.Path, Dict[pathlib.Path, str]]:
            return {path: run_git_status(path) for path in paths.values()}

        def done_callback(success: bool, result: Union[str, Dict[pathlib.Path, Dict[pathlib.Path, str]]]) -> None:
            if success and set(self.get_children()) == paths.keys():
                assert not isinstance(result, str)
                self.git_statuses = result
                self.open_and_refresh_directory(None, '')
                self.update_selection_color()
                log.debug("refreshing done")
                when_done()
            elif success:
                log.info("projects added/removed while refreshing, assuming another fresh is coming soon")
                when_done()
            else:
                log.error(f"error in git status running thread\n{result}")

        utils.run_in_thread(thread_target, done_callback, check_interval_ms=25)

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
        for path in list(path2id.keys() - new_paths):
            self.delete(path2id.pop(path))
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
                    if status in {'git_added', 'git_modified', 'git_mergeconflict'}
                    and str(subpath).startswith(str(child_path))  # optimization
                    and child_path in subpath.parents
                }
                if 'git_mergeconflict' in child_tags:
                    new_tags.add('git_mergeconflict')
                elif 'git_modified' in child_tags:
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
            ['git_added', 'git_modified', 'git_mergeconflict', None, 'git_untracked', 'git_ignored'].index(git_tag),
            1 if 'dir' in tags else 2,
            str(path),
        )

    def open_file_or_dir(self, event: object = None) -> None:
        try:
            [selected_id] = self.selection()
        except ValueError:
            # nothing selected, can happen when double-clicking something else than one of the items
            return

        if self.tag_has('dir', selected_id):
            self.open_and_refresh_directory(self.get_path(selected_id), selected_id)

            tab = get_tab_manager().select()
            if (isinstance(tab, tabs.FileTab)
                    and tab.path is not None
                    and self.get_path(selected_id) in tab.path.parents):
                # Don't know why after_idle is needed
                self.after_idle(self.select_file, tab.path)
        elif self.tag_has('file', selected_id):
            get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), self.get_path(selected_id)))

    def get_path(self, item_id: str) -> pathlib.Path:
        assert not self.tag_has('dummy', item_id)
        return pathlib.Path(self.item(item_id, 'values')[0])


def select_current_file(tree: DirectoryTree, event: object) -> None:
    tab = get_tab_manager().select()
    if isinstance(tab, tabs.FileTab) and tab.path is not None:
        tree.select_file(tab.path)


def on_new_tab(tree: DirectoryTree, tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        def path_callback(junk: object = None) -> None:
            assert isinstance(tab, tabs.FileTab)
            if tab.path is not None:
                tree.add_project(utils.find_project_root(tab.path))
                tree.refresh_everything(when_done=partial(tree.select_file, tab.path))

        path_callback()

        tab.bind('<<AfterSave>>', path_callback, add=True)
        tab.bind('<<AfterSave>>', tree.hide_old_projects, add=True)
        tab.bind('<Destroy>', tree.hide_old_projects, add=True)


def focus_treeview(tree: DirectoryTree) -> None:
    # We need to do two things:
    #   - Tell the treeview to set its focus to the first item, if no item is focused.
    #     In Tcl, this is '$tree focus', where $tree is the name of the widget.
    #   - Tell the rest of the GUI to focus the treeview. In Tcl, 'focus $tree'.
    #
    # In tkinter, both are called .focus(), and they conflict. To be explicit about
    # what focus method is being used, I decided to call the Tcl commands directly.
    if tree.get_children() and not tree.tk.call(tree, 'focus'):
        tree.tk.call(tree, 'focus', tree.get_children()[0])
    tree.tk.call('focus', tree)


# There's no way to bind so you get only main window's events.
#
# When the treeview is focused inside the Porcupine window but the Porcupine
# window itself is not focused, this refreshes twice when the window gets
# focus. If that ever becomes a problem, it can be fixed with a debouncer. At
# the time of writing this, Porcupine contains debouncer code used for
# something else. That can be found with grep.
def on_any_widget_focused(tree: DirectoryTree, event: tkinter.Event[tkinter.Misc]) -> None:
    if event.widget is get_main_window() or event.widget is tree:
        tree.refresh_everything()


def setup() -> None:
    # TODO: add something for finding a file by typing its name?
    container = ttk.Frame(get_paned_window())

    # Packing order matters. The widget packed first is always visible.
    scrollbar = ttk.Scrollbar(container)
    scrollbar.pack(side='right', fill='y')
    tree = DirectoryTree(container)
    tree.pack(side='left', fill='both', expand=True)
    get_main_window().bind('<FocusIn>', partial(on_any_widget_focused, tree), add=True)

    tree.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    get_paned_window().insert(get_tab_manager(), container)   # insert before tab manager
    get_tab_manager().add_tab_callback(partial(on_new_tab, tree))
    get_tab_manager().bind('<<NotebookTabChanged>>', partial(select_current_file, tree), add=True)

    menubar.get_menu("View").add_command(label="Focus directory tree", command=partial(focus_treeview, tree))

    settings.add_option('directory_tree_projects', [], List[str])
    string_paths = settings.get('directory_tree_projects', List[str])

    # Must reverse because last added project goes first
    for path in map(pathlib.Path, string_paths[:PROJECT_AUTOCLOSE_COUNT][::-1]):
        if path.is_absolute() and path.is_dir():
            tree.add_project(path, refresh=False)
    tree.refresh_everything()
