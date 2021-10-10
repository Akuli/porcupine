"""Displays a directory tree on the left side of the editor.

You can navigate directories, and open files in Porcupine.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import tkinter
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import Any, Callable, List

from porcupine import get_horizontal_panedwindow, get_vertical_panedwindow, get_tab_manager, menubar, settings, tabs, utils

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
_MAX_PROJECTS = 5


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


@dataclasses.dataclass
class FolderRefreshed(utils.EventDataclass):
    project_id: str
    folder_id: str


# TODO: show long paths more nicely?
def _stringify_path(path: Path) -> str:
    home = Path.home()
    if path == home or home in path.parents:
        return os.sep.join(["~"] + list(path.relative_to(home).parts))
    return str(path)


class DirectoryTree(ttk.Treeview):
    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(
            master,
            selectmode="browse",
            show="tree",
            name="directory_tree",
            style="DirectoryTree.Treeview",
        )

        # Needs after_idle because selection hasn't updated when binding runs
        self.bind("<Button-1>", self._on_click, add=True)

        self.bind("<<TreeviewOpen>>", self.open_file_or_dir, add=True)
        self.bind("<<ThemeChanged>>", self._config_tags, add=True)
        self.column("#0", minwidth=500)  # allow scrolling sideways
        self._config_tags()

        self._last_click_time = 0  # Very long time since previous click, no double click
        self._last_click_item: str | None = None

        self._project_num_counter = 0
        self.contextmenu = tkinter.Menu(tearoff=False)

        def ordered_repr(item_id: str) -> tuple[bool, str, str]:
            split_item_id = item_id.split(":", maxsplit=2)
            item_type = split_item_id[0]  # 'dir' or 'file'
            item_path = split_item_id[2]
            item_is_dotted = Path(item_path).name[0] == "."  # False < True => dot items last
            return item_is_dotted, item_type, item_path

        self.sorting_keys: list[Callable[[str], Any]] = [ordered_repr]

    def set_the_selection_correctly(self, id: str) -> None:
        self.selection_set(id)
        self.focus(id)

    def _on_click(self, event: tkinter.Event[DirectoryTree]) -> str | None:
        self.tk.call("focus", self)

        # Man page says identify_row is "obsolescent" but tkinter doesn't have the new thing yet
        item = self.identify_row(event.y)
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
            little_arrow_clicked = self.identify_element(event.x, event.y) == "Treeitem.indicator"
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
        self.tag_configure("dummy", foreground=gray)

    # This allows projects to be nested. Here's why that's a good thing:
    # Consider two projects, blah/blah/outer and blah/blah/outer/blah/inner.
    # If the inner project is not shown when outer project is already in the
    # directory tree, and home folder somehow becomes a project (e.g. when
    # editing ~/blah.py), then the directory tree will present everything
    # inside the home folder as one project.
    def add_project(self, root_path: Path, *, refresh: bool = True) -> None:
        for existing_id in self.get_children():
            if get_path(existing_id) == root_path:
                # Move project first to avoid hiding it soon
                self.move(existing_id, "", 0)
                return

        self._project_num_counter += 1
        project_item_id = f"project:{self._project_num_counter}:{root_path}"
        # insert to beginning, so it won't be hidden soon
        self.insert("", 0, project_item_id, text=_stringify_path(root_path), open=False)
        self._insert_dummy(project_item_id)
        self._hide_old_projects()
        if refresh:
            self.refresh()

    def find_project_id(self, item_id: str) -> str:
        # Does not work for dummy items, because they don't use type:num:path scheme
        num = item_id.split(":", maxsplit=2)[1]
        [result] = [id for id in self.get_children("") if id.startswith(f"project:{num}:")]
        return result

    def _find_project_id_by_path(self, path: Path) -> str | None:
        matching_projects = [
            project_id for project_id in self.get_children() if get_path(project_id) in path.parents
        ]
        if not matching_projects:
            return None

        # For ~/foo/bar/lol.py, use ~/foo/bar instead of ~/foo
        return max(matching_projects, key=(lambda id: len(str(get_path(id)))))

    def select_file(self, path: Path) -> None:
        project_id = self._find_project_id_by_path(path)
        if project_id is None:
            # Happens when tab changes because a file was just opened. This
            # will be called soon once the project has been added.
            log.info(f"can't select '{path}' because there are no projects containing it")
            return

        project_root_path = get_path(project_id)

        # Find the visible sub-item representing the file
        file_id = project_id
        subpath = project_root_path
        for part in path.relative_to(project_root_path).parts:
            subpath /= part
            if self.item(file_id, "open"):
                mypy_sucks = self.get_id_from_path(subpath, project_id)
                assert mypy_sucks is not None
                file_id = mypy_sucks
            else:
                # ...or a closed folder that contains the file
                break

        self.set_the_selection_correctly(file_id)
        self.see(file_id)

    def _insert_dummy(self, parent: str, *, text: str = "", clear: bool = False) -> None:
        assert parent
        if clear:
            self.delete(*self.get_children(parent))
        else:
            assert not self.get_children(parent)

        self.insert(parent, "end", text=text, tags="dummy")

    def contains_dummy(self, parent: str) -> bool:
        children = self.get_children(parent)
        return len(children) == 1 and self.tag_has("dummy", children[0])

    # TODO: it's not great how only the directory tree knows this
    def project_has_open_filetabs(self, project_id: str) -> bool:
        assert project_id.startswith("project:")
        return any(
            isinstance(tab, tabs.FileTab)
            and tab.path is not None
            and self._find_project_id_by_path(tab.path) == project_id
            for tab in get_tab_manager().tabs()
        )

    def _hide_old_projects(self, junk: object = None) -> None:
        for project_id in self.get_children(""):
            if not get_path(project_id).is_dir():
                self.delete(project_id)

        # To avoid getting rid of existing projects when not necessary, we do
        # shortening after deleting non-existent projects
        for project_id in reversed(self.get_children("")):
            if len(self.get_children("")) > _MAX_PROJECTS and not self.project_has_open_filetabs(
                project_id
            ):
                self.delete(project_id)

        self.save_project_list()

    def save_project_list(self) -> None:
        # Settings is a weird place for this, but easier than e.g. using a cache file.
        settings.set_("directory_tree_projects", [str(get_path(id)) for id in self.get_children()])

    def refresh(self, junk: object = None) -> None:
        log.debug("refreshing begins")
        self._hide_old_projects()
        self.event_generate("<<RefreshBegins>>")
        for project_id in self.get_children():
            self._update_tags_and_content(get_path(project_id), project_id)

    # The following two methods call each other recursively.

    def _update_tags_and_content(self, project_root: Path, child_id: str) -> None:
        if child_id.startswith(("dir:", "project:")) and not self.contains_dummy(child_id):
            self._open_and_refresh_directory(child_id)

    def _open_and_refresh_directory(self, dir_id: str) -> None:
        dir_path = get_path(dir_id)

        if self.contains_dummy(dir_id):
            self.delete(self.get_children(dir_id)[0])

        project_ids = self.get_children("")
        if dir_id not in project_ids and dir_path in map(get_path, project_ids):
            self._insert_dummy(dir_id, text="(open as a separate project)", clear=True)
            return

        new_paths = set(dir_path.iterdir())
        path2id = {get_path(id): id for id in self.get_children(dir_id)}

        # TODO: handle changing directory to file
        for path in list(path2id.keys() - new_paths):
            self.delete(path2id.pop(path))
        for path in list(new_paths - path2id.keys()):
            project_num = dir_id.split(":", maxsplit=2)[1]
            if path.is_dir():
                item_id = f"dir:{project_num}:{path}"
            else:
                item_id = f"file:{project_num}:{path}"

            self.insert(dir_id, "end", item_id, text=path.name, open=False)
            path2id[path] = item_id
            if path.is_dir():
                self._insert_dummy(item_id)

        project_id = self.find_project_id(dir_id)
        project_root = get_path(project_id)
        for child_path, child_id in path2id.items():
            self._update_tags_and_content(project_root, child_id)
        self.sort_folder_contents(dir_id)

        if not self.get_children(dir_id):
            self._insert_dummy(dir_id, text="(empty)")

        # When binding, delete tags from previous call
        self.event_generate(
            "<<FolderRefreshed>>", data=FolderRefreshed(project_id=project_id, folder_id=dir_id)
        )

    def sort_folder_contents(self, dir_id: str) -> None:
        # Empty string is root element and sorting inside it would mess with order of projects
        assert dir_id

        for index, child_id in enumerate(
            sorted(
                self.get_children(dir_id),
                key=(lambda item_id: [f(item_id) for f in self.sorting_keys]),
            )
        ):
            self.move(child_id, dir_id, index)

    def open_file_or_dir(self, event: object = None) -> None:
        try:
            [selected_id] = self.selection()
        except ValueError:
            # nothing selected, can happen when double-clicking something else than one of the items
            return

        if selected_id.startswith("file:"):
            get_tab_manager().open_file(get_path(selected_id))
        elif selected_id.startswith(("dir:", "project:")):  # not dummy item
            self._open_and_refresh_directory(selected_id)

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

        if self.exists(result):
            return result
        return None

    def _cycle_through_items(self, event: tkinter.Event[DirectoryTree]) -> None:
        if len(event.char) != 1:
            return

        try:
            [item] = self.selection()
        except ValueError:  # nothing selected
            return

        children = [
            c
            for c in self.get_children(self.parent(item))
            if self.item(c, "text").startswith(event.char)
        ]
        if not children:
            return

        try:
            index = (children.index(item) + 1) % len(children)
        except ValueError:
            index = 0

        self.set_the_selection_correctly(children[index])
        self.see(children[index])

    def _on_right_click(self, event: tkinter.Event[DirectoryTree]) -> str | None:
        self.tk.call("focus", self)

        item: str = self.identify_row(event.y)
        self.set_the_selection_correctly(item)

        self.contextmenu.delete(0, "end")
        self.event_generate("<<PopulateContextMenu>>")
        if self.contextmenu.index("end") is not None:
            # Menu is not empty
            self.contextmenu.tk_popup(event.x_root, event.y_root)
        return "break"


def _select_current_file(tree: DirectoryTree, event: object) -> None:
    tab = get_tab_manager().select()
    if isinstance(tab, tabs.FileTab) and tab.path is not None:
        tree.select_file(tab.path)


def _on_new_filetab(tree: DirectoryTree, tab: tabs.FileTab) -> None:
    def path_callback(junk: object = None) -> None:
        if tab.path is not None:
            # directory tree should already contain the path
            tree.add_project(utils.find_project_root(tab.path))
            tree.select_file(tab.path)

    path_callback()

    tab.bind("<<AfterSave>>", path_callback, add=True)
    tab.bind("<<AfterSave>>", tree._hide_old_projects, add=True)
    tab.bind("<Destroy>", tree._hide_old_projects, add=True)


def _focus_treeview(tree: DirectoryTree) -> None:
    if tree.get_children() and not tree.focus():
        tree.set_the_selection_correctly(tree.get_children()[0])

    # Tkinter has two things called .focus(), and they conflict:
    #  - Telling the treeview to set its focus to the first item, if no item is
    #    focused. In Tcl, '$tree focus', where $tree is the widget name. This
    #    is what the .focus() method does.
    #  - Tell the rest of the GUI to focus the treeview. In Tcl, 'focus $tree'.
    tree.tk.call("focus", tree)


def setup() -> None:
    settings.add_option("directory_tree_projects", [], List[str])

    container = ttk.Frame(get_horizontal_panedwindow(), name="directory_tree_container")
    get_horizontal_panedwindow().add(container, before=get_vertical_panedwindow())
    settings.remember_pane_size(get_horizontal_panedwindow(), container, "directory_tree_width", 200)

    # Packing order matters. The widget packed first is always visible.
    scrollbar = ttk.Scrollbar(container)
    scrollbar.pack(side="right", fill="y")
    tree = DirectoryTree(container)
    tree.pack(side="left", fill="both", expand=True)
    get_tab_manager().bind("<<FileSystemChanged>>", tree.refresh, add=True)

    tree.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    get_tab_manager().add_filetab_callback(partial(_on_new_filetab, tree))
    get_tab_manager().bind("<<NotebookTabChanged>>", partial(_select_current_file, tree), add=True)

    menubar.get_menu("View").add_command(
        label="Focus directory tree", command=partial(_focus_treeview, tree)
    )

    # Must reverse because last added project goes first
    string_paths = settings.get("directory_tree_projects", List[str])
    for path in map(Path, string_paths[:_MAX_PROJECTS][::-1]):
        if path.is_absolute() and path.is_dir():
            tree.add_project(path, refresh=False)
    tree.refresh()

    # TODO: invoking context menu from keyboard
    tree.bind("<<RightClick>>", tree._on_right_click, add=True)

    tree.bind("<Key>", tree._cycle_through_items, add=True)


# Used in other plugins
def get_directory_tree() -> DirectoryTree:
    return get_horizontal_panedwindow().nametowidget("directory_tree_container.directory_tree")
