from __future__ import annotations

import logging
import pathlib
import subprocess
import sys
import time
import tkinter
from functools import partial
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from porcupine import (
    get_main_window,
    get_paned_window,
    get_tab_manager,
    menubar,
    settings,
    tabs,
    utils,
)

log = logging.getLogger(__name__)

# The idea: If more than this many projects are opened, then the least recently
# opened project will be closed.
#
# Gotchas:
#   - Git run time is the bottleneck of refreshing, and it's proportional to
#     this. For that reason, keep it small.
#   - If you have more than this many files open, each from a different
#     project, there will be one project for each file in the directory tree
#     and this number is exceeded.
MAX_PROJECTS = 5


def run_git_status(project_root: pathlib.Path) -> Dict[pathlib.Path, str]:
    try:
        start = time.perf_counter()
        run_result = subprocess.run(
            ["git", "status", "--ignored", "--porcelain"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # for logging error message
            encoding=sys.getfilesystemencoding(),
            **utils.subprocess_kwargs,
        )
        log.debug(f"git ran in {round((time.perf_counter() - start)*1000)}ms")

        if run_result.returncode != 0:
            # likely not a git repo because missing ".git" dir
            log.info(f"git failed in {project_root}: {run_result}")
            return {}

    except (OSError, UnicodeError):
        log.warning("can't run git", exc_info=True)
        return {}

    # Show .git as ignored, even though it actually isn't
    result = {project_root / ".git": "git_ignored"}
    for line in run_result.stdout.splitlines():
        path = project_root / line[3:]
        if line[1] == "M":
            result[path] = "git_modified"
        elif line[1] == " ":
            result[path] = "git_added"
        elif line[:2] == "??":
            result[path] = "git_untracked"
        elif line[:2] == "!!":
            result[path] = "git_ignored"
        elif line[:2] in {"AA", "UU"}:
            result[path] = "git_mergeconflict"
        else:
            log.warning(f"unknown git status line: {repr(line)}")
    return result


# For perf reasons, we want to avoid unnecessary Tcl calls when
# looking up information by id. Easiest solution is to include the
# information in the id. It's a bit lol. The format is:
#
#   "{type}:{project_number}:{path}"
#
# where:
#   - type is "file", "dir", "project"
#   - project_number is unique to each project
def get_path(item_id: str) -> pathlib.Path:
    item_type, project_number, path = item_id.split(":", maxsplit=2)
    return pathlib.Path(path)


class DirectoryTree(ttk.Treeview):
    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode="browse", show="tree", style="DirectoryTree.Treeview")

        # Needs after_idle because selection hasn't updated when binding runs
        self.bind("<Button-1>", (lambda event: self.after_idle(self.on_click, event)), add=True)

        self.bind("<<TreeviewOpen>>", self.open_file_or_dir, add=True)
        self.bind("<<TreeviewSelect>>", self.update_selection_color, add=True)
        self.bind("<<ThemeChanged>>", self._config_tags, add=True)
        self.column("#0", minwidth=500)  # allow scrolling sideways
        self._config_tags()
        self.git_statuses: Dict[pathlib.Path, Dict[pathlib.Path, str]] = {}

        self._last_click_time = 0
        self._last_click_selection: Optional[Tuple[str, ...]] = None

        self._project_num_counter = 0

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
        fg = self.tk.eval("ttk::style lookup Treeview -foreground")
        bg = self.tk.eval("ttk::style lookup Treeview -background")
        gray = utils.mix_colors(fg, bg, 0.5)

        if sum(self.winfo_rgb(fg)) > 3 * 0x7FFF:
            # bright foreground color
            green = "#00ff00"
            orange = "#ff6e00"
        else:
            green = "#007f00"
            orange = "#e66300"

        self.tag_configure("dummy", foreground=gray)
        self.tag_configure("git_mergeconflict", foreground=orange)
        self.tag_configure("git_modified", foreground="red")
        self.tag_configure("git_added", foreground=green)
        self.tag_configure("git_untracked", foreground="red4")
        self.tag_configure("git_ignored", foreground=gray)

    def update_selection_color(self, event: object = None) -> None:
        try:
            [selected_id] = self.selection()
        except ValueError:  # nothing selected
            git_tags = []
        else:
            git_tags = [tag for tag in self.item(selected_id, "tags") if tag.startswith("git_")]

        if git_tags:
            [tag] = git_tags
            color = self.tag_configure(tag, "foreground")
            self.tk.call(
                "ttk::style", "map", "DirectoryTree.Treeview", "-foreground", ["selected", color]
            )
        else:
            # use default colors
            self.tk.eval("ttk::style map DirectoryTree.Treeview -foreground {}")

    # This allows projects to be nested. Here's why that's a good thing:
    # Consider two projects, blah/blah/outer and blah/blah/outer/blah/inner.
    # If the inner project is not shown when outer project is already in the
    # directory tree, and home folder somehow becomes a project (e.g. when
    # editing ~/blah.py), then the directory tree will present everything
    # inside the home folder as one project.
    def add_project(self, root_path: pathlib.Path, *, refresh: bool = True) -> None:
        for project_item_id in self.get_children():
            if get_path(project_item_id) == root_path:
                # Move project first to avoid hiding it soon
                self.move(project_item_id, "", 0)  # type: ignore[no-untyped-call]
                return

        # TODO: show long paths more nicely
        text = str(root_path)
        if pathlib.Path.home() in root_path.parents:
            text = text.replace(str(pathlib.Path.home()), "~", 1)

        # Add project to beginning so it won't be hidden soon
        self._project_num_counter += 1
        project_item_id = self.insert(
            "", 0, f"project:{self._project_num_counter}:{root_path}", text=text, open=False
        )
        self._insert_dummy(project_item_id)
        self.hide_old_projects()
        if refresh:
            self.refresh_everything()

    def set_the_selection_correctly(self, id: str) -> None:
        self.selection_set(id)  # type: ignore[no-untyped-call]
        self.focus(id)

    def select_file(self, path: pathlib.Path) -> None:
        for project_root_id in self.get_children():
            project_root = get_path(project_root_id)
            if project_root not in path.parents:
                continue

            # Find the sub-item representing the file
            file_id = project_root_id
            for part in path.relative_to(project_root).parts:
                if self.item(file_id, "open"):
                    [file_id] = [
                        child
                        for child in self.get_children(file_id)
                        if get_path(child).name == part
                    ]
                else:
                    # ...or a closed folder that contains the file
                    break

            self.set_the_selection_correctly(file_id)
            self.see(file_id)  # type: ignore[no-untyped-call]

            # Multiple projects may match when project roots are nested. It's
            # fine to use the first match, because recently used projects tend
            # to go first.
            return

        # Happens when tab changes because a file was just opened. This
        # will be called soon once the project has been added.
        log.info(f"can't select '{path}' because its project was not found")

    def _insert_dummy(self, parent: str) -> None:
        assert parent
        assert not self.get_children(parent)
        self.insert(parent, "end", text="(empty)", tags="dummy")

    def contains_dummy(self, parent: str) -> bool:
        children = self.get_children(parent)
        return len(children) == 1 and self.tag_has("dummy", children[0])

    def hide_old_projects(self, junk: object = None) -> None:
        for project_id in self.get_children(""):
            if not get_path(project_id).is_dir():
                self.delete(project_id)  # type: ignore[no-untyped-call]

        # To avoid getting rid of existing projects when not necessary, we do
        # shortening after deleting non-existent projects
        for project_id in reversed(self.get_children("")):
            if len(self.get_children("")) > MAX_PROJECTS and not any(
                isinstance(tab, tabs.FileTab)
                and tab.path is not None
                and get_path(project_id) in tab.path.parents
                for tab in get_tab_manager().tabs()
            ):
                self.delete(project_id)  # type: ignore[no-untyped-call]

        # Settings is a weird place for this, but easier than e.g. using a cache file.
        settings.set_("directory_tree_projects", [str(get_path(id)) for id in self.get_children()])

    def refresh_everything(
        self, junk: object = None, *, when_done: Callable[[], None] = (lambda: None)
    ) -> None:
        log.debug("refreshing begins")
        start_time = time.time()
        self.hide_old_projects()
        project_ids = self.get_children()

        def thread_target() -> dict[pathlib.Path, dict[pathlib.Path, str]]:
            return {path: run_git_status(path) for path in map(get_path, project_ids)}

        def done_callback(
            success: bool, result: str | dict[pathlib.Path, dict[pathlib.Path, str]]
        ) -> None:
            log.debug(f"thread done in {round((time.time()-start_time)*1000)}ms")
            if success and set(self.get_children()) == set(project_ids):
                assert isinstance(result, dict)
                self.git_statuses = result
                for project_id in self.get_children(""):
                    self._update_tags_and_content(get_path(project_id), project_id)
                self.update_selection_color()
                log.debug(f"refreshing done in {round((time.time()-start_time)*1000)}ms")
                when_done()
            elif success:
                log.info(
                    "projects added/removed while refreshing, assuming another fresh is coming soon"
                )
                when_done()
            else:
                log.error(f"error in git status running thread\n{result}")

        utils.run_in_thread(thread_target, done_callback, check_interval_ms=25)

    def _find_project_id(self, item_id: str) -> str:
        # Does not work for dummy items, because they don't use type:num:path scheme
        num = item_id.split(":", maxsplit=2)[1]
        [result] = [id for id in self.get_children("") if id.startswith(f"project:{num}:")]
        return result

    # The following two functions call each other recursively.

    def _update_tags_and_content(self, project_root: pathlib.Path, child_id: str) -> None:
        child_path = get_path(child_id)
        path_to_status = self.git_statuses[project_root]

        # Search for status, from child_path to project_root inclusive
        path = child_path
        while path not in path_to_status and path != project_root:
            path = path.parent

        try:
            status: str | None = path_to_status[path]
        except KeyError:
            # Handle directories containing files with different statuses
            substatuses = {
                s
                for p, s in path_to_status.items()
                if s in {"git_added", "git_modified", "git_mergeconflict"}
                and child_path in p.parents
            }

            if "git_mergeconflict" in substatuses:
                status = "git_mergeconflict"
            elif "git_modified" in substatuses:
                status = "git_modified"
            elif "git_added" in substatuses:
                status = "git_added"
            else:
                assert not substatuses
                status = None

        self.item(child_id, tags=([] if status is None else status))
        if child_id.startswith(("dir:", "project:")) and not self.contains_dummy(child_id):
            self.open_and_refresh_directory(child_path, child_id)

    def open_and_refresh_directory(self, dir_path: pathlib.Path, dir_id: str) -> None:
        if self.contains_dummy(dir_id):
            self.delete(self.get_children(dir_id)[0])  # type: ignore[no-untyped-call]

        path2id = {get_path(id): id for id in self.get_children(dir_id)}
        new_paths = set(dir_path.iterdir())
        if not new_paths:
            for child in self.get_children(dir_id):
                self.delete(child)
            self._insert_dummy(dir_id)
            return

        # TODO: handle changing directory to file
        for path in list(path2id.keys() - new_paths):
            self.delete(path2id.pop(path))  # type: ignore[no-untyped-call]
        for path in list(new_paths - path2id.keys()):
            project_num = dir_id.split(":", maxsplit=2)[1]
            if path.is_dir():
                item_id = f"dir:{project_num}:{path}"
            else:
                item_id = f"file:{project_num}:{path}"

            path2id[path] = self.insert(dir_id, "end", item_id, text=path.name, open=False)
            if path.is_dir():
                assert dir_path is not None
                self._insert_dummy(path2id[path])

        project_root = get_path(self._find_project_id(dir_id))
        for child_path, child_id in path2id.items():
            self._update_tags_and_content(project_root, child_id)

        for index, child_id in enumerate(sorted(self.get_children(dir_id), key=self._sorting_key)):
            self.move(child_id, dir_id, index)  # type: ignore[no-untyped-call]

    def _sorting_key(self, item_id: str) -> Tuple[Any, ...]:
        [git_tag] = self.item(item_id, "tags") or [None]

        return (
            [
                "git_added",
                "git_modified",
                "git_mergeconflict",
                None,
                "git_untracked",
                "git_ignored",
            ].index(git_tag),
            item_id,  # "dir" before "file", sort each by path
        )

    def open_file_or_dir(self, event: object = None) -> None:
        try:
            [selected_id] = self.selection()
        except ValueError:
            # nothing selected, can happen when double-clicking something else than one of the items
            return

        if selected_id.startswith("file:"):
            get_tab_manager().add_tab(
                tabs.FileTab.open_file(get_tab_manager(), get_path(selected_id))
            )
        elif selected_id.startswith(("dir:", "project:")):  # not dummy item
            self.open_and_refresh_directory(get_path(selected_id), selected_id)

            tab = get_tab_manager().select()
            if (
                isinstance(tab, tabs.FileTab)
                and tab.path is not None
                and get_path(selected_id) in tab.path.parents
            ):
                # Don't know why after_idle is needed
                self.after_idle(self.select_file, tab.path)


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

        tab.bind("<<AfterSave>>", path_callback, add=True)
        tab.bind("<<AfterSave>>", tree.hide_old_projects, add=True)
        tab.bind("<Destroy>", tree.hide_old_projects, add=True)


def focus_treeview(tree: DirectoryTree) -> None:
    if tree.get_children() and not tree.focus():
        tree.set_the_selection_correctly(tree.get_children()[0])

    # Tkinter has two things called .focus(), and they conflict:
    #  - Telling the treeview to set its focus to the first item, if no item is
    #    focused. In Tcl, '$tree focus', where $tree is the widget name. This
    #    is what the .focus() method does.
    #  - Tell the rest of the GUI to focus the treeview. In Tcl, 'focus $tree'.
    tree.tk.call("focus", tree)


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
    scrollbar.pack(side="right", fill="y")
    tree = DirectoryTree(container)
    tree.pack(side="left", fill="both", expand=True)
    get_main_window().bind("<FocusIn>", partial(on_any_widget_focused, tree), add=True)

    tree.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    # Insert directory tree before tab manager
    get_paned_window().insert(get_tab_manager(), container)  # type: ignore[no-untyped-call]

    get_tab_manager().add_tab_callback(partial(on_new_tab, tree))
    get_tab_manager().bind("<<NotebookTabChanged>>", partial(select_current_file, tree), add=True)

    menubar.get_menu("View").add_command(
        label="Focus directory tree", command=partial(focus_treeview, tree)
    )

    settings.add_option("directory_tree_projects", [], List[str])
    string_paths = settings.get("directory_tree_projects", List[str])

    # Must reverse because last added project goes first
    for path in map(pathlib.Path, string_paths[:MAX_PROJECTS][::-1]):
        if path.is_absolute() and path.is_dir():
            tree.add_project(path, refresh=False)
    tree.refresh_everything()
