from __future__ import annotations

import dataclasses
import logging
import os
import subprocess
import sys
import time
import tkinter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable, Dict, Iterator, List, Tuple

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


def run_git_status(project_root: Path) -> Dict[Path, str]:
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
            log.debug(f"git failed in {project_root}: {run_result}")
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
    print("git status:", project_root, "-->", result)
    return result


# Each git subprocess uses one cpu core
_git_pool = ThreadPoolExecutor(max_workers=os.cpu_count())


# For perf reasons, we want to avoid unnecessary Tcl calls when
# looking up information by id. Easiest solution is to include the
# information in the id. It's a bit lol. The format is:
#
#   "{type}:{project_number}:{path}"
#
# where:
#   - type is "file", "dir", "project"
#   - project_number is unique to each project
def get_path(item_id: str) -> Path:
    item_type, project_number, path = item_id.split(":", maxsplit=2)
    return Path(path)


def _path_to_root_inclusive(path: Path, root: Path) -> Iterator[Path]:
    assert path == root or root in path.parents
    while True:
        yield path
        if path == root:
            break
        path = path.parent


@dataclasses.dataclass
class FolderRefreshed(utils.EventDataclass):
    project_id: str
    folder_id: str


class DirectoryTree(ttk.Treeview):
    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode="browse", show="tree", style="DirectoryTree.Treeview")

        # Needs after_idle because selection hasn't updated when binding runs
        self.bind("<Button-1>", self._on_click, add=True)

        self.bind("<<TreeviewOpen>>", self.open_file_or_dir, add=True)
        self.bind("<<TreeviewSelect>>", self._update_selection_color, add=True)
        self.bind("<<ThemeChanged>>", self._config_tags, add=True)
        self.column("#0", minwidth=500)  # allow scrolling sideways
        self._config_tags()
        self.git_statuses: Dict[Path, Dict[Path, str]] = {}

        self._last_click_time = 0  # Very long time since previous click, no double click
        self._last_click_item: str | None = None

        self._project_num_counter = 0

    def set_the_selection_correctly(self, id: str) -> None:
        self.selection_set(id)  # type: ignore[no-untyped-call]
        self.focus(id)

    def _on_click(self, event: tkinter.Event[DirectoryTree]) -> str | None:
        self.tk.call("focus", self)

        # Man page says identify_row is "obsolescent" but tkinter doesn't have the new thing yet
        item = self.identify_row(event.y)  # type: ignore[no-untyped-call]
        if item is None:
            return None

        # Couldn't get <Double-Button-1> to work, so I wrote a program to
        # measure max time between double clicks. It's 500ms on my system.
        double_click = event.time - self._last_click_time < 500 and self._last_click_item == item

        self.set_the_selection_correctly(item)
        if item.startswith("file:"):
            if double_click:
                self.open_file_or_dir()
        else:
            little_arrow_clicked = self.identify_element(event.x, event.y) == "Treeitem.indicator"  # type: ignore[no-untyped-call]
            if double_click or little_arrow_clicked:
                self.item(item, open=(not self.item(item, "open")))
                if self.item(item, "open"):
                    self.open_file_or_dir()

        self._last_click_item = item
        if double_click:
            # Prevent getting two double clicks with 3 quick subsequent clicks
            self._last_click_time = 0
        else:
            self._last_click_time = event.time
        return "break"

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

    def _update_selection_color(self, event: object = None) -> None:
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
    def add_project(self, root_path: Path, *, refresh: bool = True) -> None:
        for project_item_id in self.get_children():
            if get_path(project_item_id) == root_path:
                # Move project first to avoid hiding it soon
                self.move(project_item_id, "", 0)  # type: ignore[no-untyped-call]
                return

        # TODO: show long paths more nicely
        text = str(root_path)
        if Path.home() in root_path.parents:
            text = text.replace(str(Path.home()), "~", 1)

        # Add project to beginning so it won't be hidden soon
        self._project_num_counter += 1
        project_item_id = self.insert(
            "", 0, f"project:{self._project_num_counter}:{root_path}", text=text, open=False
        )
        self._insert_dummy(project_item_id)
        self._hide_old_projects()
        if refresh:
            self.refresh()

    def select_file(self, path: Path) -> None:
        for project_id in self.get_children():
            if get_path(project_id) not in path.parents:
                continue

            path_to_root = list(_path_to_root_inclusive(path, get_path(project_id)))
            root_to_path_excluding_root = path_to_root[::-1][1:]

            # Find the visible sub-item representing the file
            file_id = project_id
            for subpath in root_to_path_excluding_root:
                if self.item(file_id, "open"):
                    file_id = self.get_id_from_path(subpath, project_id)
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

    def _hide_old_projects(self, junk: object = None) -> None:
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

    def refresh(
        self, junk: object = None, *, done_callback: Callable[[], None] = (lambda: None)
    ) -> None:
        log.debug("refreshing begins")
        start_time = time.time()
        self._hide_old_projects()
        project_ids = self.get_children("")
        git_futures = {
            path: _git_pool.submit(partial(run_git_status, path))
            for path in map(get_path, project_ids)
        }

        def check_if_done() -> None:
            print("check if done")
            if not all(future.done() for future in git_futures.values()):
                print("  need other check")
                self.after(25, check_if_done)
                return

            if set(self.get_children()) == set(project_ids):
                print("  projects same")
                self.git_statuses = {path: future.result() for path, future in git_futures.items()}
                print("  self.git_statuses =", self.git_statuses)
                for project_id in self.get_children(""):
                    self._update_tags_and_content(get_path(project_id), project_id)
                self._update_selection_color()
                log.info(f"refreshing done in {round((time.time()-start_time)*1000)}ms")
            else:
                print("  projects ch")
                log.info(
                    "projects added/removed while refreshing, assuming another fresh is coming soon"
                )

            done_callback()

        check_if_done()

    def find_project_id(self, item_id: str) -> str:
        # Does not work for dummy items, because they don't use type:num:path scheme
        num = item_id.split(":", maxsplit=2)[1]
        [result] = [id for id in self.get_children("") if id.startswith(f"project:{num}:")]
        return result

    # The following two methods call each other recursively.

    def _update_tags_and_content(self, project_root: Path, child_id: str) -> None:
        child_path = get_path(child_id)
        path_to_status = self.git_statuses[project_root]

        for path in _path_to_root_inclusive(child_path, project_root):
            try:
                status: str | None = path_to_status[path]
                break
            except KeyError:
                continue
        else:
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
            self._open_and_refresh_directory(child_path, child_id)

    def _open_and_refresh_directory(self, dir_path: Path, dir_id: str) -> None:
        if self.contains_dummy(dir_id):
            self.delete(self.get_children(dir_id)[0])  # type: ignore[no-untyped-call]

        path2id = {get_path(id): id for id in self.get_children(dir_id)}
        new_paths = set(dir_path.iterdir())
        if not new_paths:
            for child in self.get_children(dir_id):
                self.delete(child)  # type: ignore[no-untyped-call]
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

        project_id = self.find_project_id(dir_id)
        project_root = get_path(project_id)
        for child_path, child_id in path2id.items():
            self._update_tags_and_content(project_root, child_id)

        for index, child_id in enumerate(sorted(self.get_children(dir_id), key=self._sorting_key)):
            self.move(child_id, dir_id, index)  # type: ignore[no-untyped-call]

        # When binding to this event, make sure you delete all tags you created on previous update.
        # Even though refersh() deletes tags, this method by itself doesn't.
        self.event_generate(
            "<<FolderRefreshed>>", data=FolderRefreshed(project_id=project_id, folder_id=dir_id)
        )

    def _sorting_key(self, item_id: str) -> Tuple[Any, ...]:
        [git_tag] = [t for t in self.item(item_id, "tags") if t.startswith("git_")] or [None]

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
            self._open_and_refresh_directory(get_path(selected_id), selected_id)

            tab = get_tab_manager().select()
            if (
                isinstance(tab, tabs.FileTab)
                and tab.path is not None
                and get_path(selected_id) in tab.path.parents
            ):
                # Don't know why after_idle is needed
                self.after_idle(self.select_file, tab.path)

    def get_id_from_path(self, path: Path, project_id: str) -> str | None:
        """Find an item from the directory tree given its path.

        Because the treeview loads items lazily as needed, this may return None
        even if the path exists inside the project.
        """
        project_num = project_id.split(":", maxsplit=2)[1]
        if path.is_dir():
            result = f"dir:{project_num}:{path}"
        else:
            result = f"file:{project_num}:{path}"

        if self.exists(result):  # type: ignore[no-untyped-call]
            return result
        return None


def select_current_file(tree: DirectoryTree, event: object) -> None:
    tab = get_tab_manager().select()
    if isinstance(tab, tabs.FileTab) and tab.path is not None:
        tree.select_file(tab.path)


def on_new_filetab(tree: DirectoryTree, tab: tabs.FileTab) -> None:
    def path_callback(junk: object = None) -> None:
        if tab.path is not None:
            tree.add_project(utils.find_project_root(tab.path))
            tree.refresh(done_callback=partial(tree.select_file, tab.path))

    path_callback()

    tab.bind("<<AfterSave>>", path_callback, add=True)
    tab.bind("<<AfterSave>>", tree._hide_old_projects, add=True)
    tab.bind("<Destroy>", tree._hide_old_projects, add=True)


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
        tree.refresh()


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

    get_tab_manager().add_filetab_callback(partial(on_new_filetab, tree))
    get_tab_manager().bind("<<NotebookTabChanged>>", partial(select_current_file, tree), add=True)

    menubar.get_menu("View").add_command(
        label="Focus directory tree", command=partial(focus_treeview, tree)
    )

    settings.add_option("directory_tree_projects", [], List[str])
    string_paths = settings.get("directory_tree_projects", List[str])

    # Must reverse because last added project goes first
    for path in map(Path, string_paths[:MAX_PROJECTS][::-1]):
        if path.is_absolute() and path.is_dir():
            tree.add_project(path, refresh=False)
    tree.refresh()
