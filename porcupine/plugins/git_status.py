"""Color items in the directory tree based on their git status."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from porcupine import utils
from porcupine.plugins.directory_tree import (
    DirectoryTree,
    FolderRefreshed,
    get_directory_tree,
    get_path,
)

setup_after = ["directory_tree"]

log = logging.getLogger(__name__)

# Each git subprocess uses one cpu core
git_pool = ThreadPoolExecutor(max_workers=os.cpu_count())


def run_git_status(project_root: Path) -> dict[Path, str]:
    try:
        start = time.perf_counter()
        run_result = subprocess.run(
            # For debugging: ["bash", "-c", "sleep 1 && git status --ignored --porcelain"],
            ["git", "status", "--ignored", "--porcelain"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # for logging error message
            encoding=sys.getfilesystemencoding(),
            timeout=2,  # huge lol
            **utils.subprocess_kwargs,
        )
        log.debug(
            f"running git status in {project_root} took"
            f" {round((time.perf_counter() - start)*1000)}ms"
        )

        if run_result.returncode != 0:
            # likely not a git repo because missing ".git" dir
            log.debug(f"git status failed in {project_root}: {run_result}")
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

    # When a folder contains files with different statuses, decide status of folder
    # There can be lots of statuses, not good to loop through them in gui thread
    folder_to_content_statuses: dict[Path, set[str]] = {}
    for path, status in result.items():
        if status in {"git_added", "git_modified", "git_mergeconflict"}:
            for folder in path.parents:
                folder_to_content_statuses.setdefault(folder, set()).add(status)
                if folder == project_root:
                    break

    assert not (folder_to_content_statuses.keys() & result.keys())

    for folder, content_statuses in folder_to_content_statuses.items():
        if "git_mergeconflict" in content_statuses:
            result[folder] = "git_mergeconflict"
        elif "git_modified" in content_statuses:
            result[folder] = "git_modified"
        elif "git_added" in content_statuses:
            result[folder] = "git_added"
        else:
            raise RuntimeError("this shouldn't happen")

    return result


class ProjectColorer:
    def __init__(self, tree: DirectoryTree, project_id: str):
        self.tree = tree
        self.project_id = project_id
        self.project_path = get_path(project_id)
        self.queue: set[str] = set()
        self._git_status_future: Future[dict[Path, str]] | None = None

    def start_running_git_status(self) -> None:
        self._git_status_future = git_pool.submit(partial(run_git_status, self.project_path))

        # Handle queue contents when it has completed
        def check() -> None:
            if self._git_status_future is not None:
                if self._git_status_future.done():
                    self._handle_queue()
                else:
                    self.tree.after(25, check)

        check()

    def stop(self) -> None:
        self._git_status_future = None

    def _choose_tag(self, item_path: Path) -> str | None:
        # process should be done, result available immediately
        assert self._git_status_future is not None
        path_to_status = self._git_status_future.result(timeout=0)
        return path_to_status.get(item_path)

    def _set_tag(self, item_id: str, git_tag: str | None) -> bool:
        old_tags = set(self.tree.item(item_id, "tags"))
        new_tags = {tag for tag in old_tags if not tag.startswith("git_")}
        if git_tag is not None:
            new_tags.add(git_tag)

        if old_tags == new_tags:
            return False

        self.tree.item(item_id, tags=list(new_tags))
        if item_id in self.tree.selection():
            update_tree_selection_color(self.tree)
        return True

    def _handle_queue(self) -> None:
        while self.queue:
            dir_id = self.queue.pop()

            if not self.tree.contains_dummy(dir_id):
                tags_changed = False
                for item_id in self.tree.get_children(dir_id):
                    if self._set_tag(item_id, self._choose_tag(get_path(item_id))):
                        tags_changed = True
                if tags_changed:
                    self.tree.sort_folder_contents(dir_id)

            if dir_id.startswith("project:"):
                self._set_tag(dir_id, self._choose_tag(get_path(dir_id)))

    def color_children_now_or_later(self, parent_id: str) -> None:
        self.queue.add(parent_id)
        assert self._git_status_future is not None
        if self._git_status_future.done():
            self._handle_queue()


# not project-specific
class TreeColorer:
    def __init__(self, tree: DirectoryTree):
        self.tree = tree
        self.project_specific_colorers: dict[str, ProjectColorer] = {}

    def config_color_tags(self, junk: object = None) -> None:
        fg = self.tree.tk.eval("ttk::style lookup Treeview -foreground")
        bg = self.tree.tk.eval("ttk::style lookup Treeview -background")
        gray = utils.mix_colors(fg, bg, 0.5)

        if utils.is_bright(fg):
            green = "#00ff00"
            orange = "#ff6e00"
        else:
            green = "#007f00"
            orange = "#e66300"

        self.tree.tag_configure("git_mergeconflict", foreground=orange)
        self.tree.tag_configure("git_modified", foreground="red")
        self.tree.tag_configure("git_added", foreground=green)
        self.tree.tag_configure("git_untracked", foreground="red4")
        self.tree.tag_configure("git_ignored", foreground=gray)

    def start_status_coloring_for_all_projects(self, junk_event: object) -> None:
        for colorer in self.project_specific_colorers.values():
            colorer.stop()
        self.project_specific_colorers.clear()

        for project_id in self.tree.get_children():
            colorer = ProjectColorer(self.tree, project_id)
            self.project_specific_colorers[project_id] = colorer
            colorer.queue.add(project_id)
            colorer.start_running_git_status()

    def color_child_items(self, event: utils.EventWithData) -> None:
        info = event.data_class(FolderRefreshed)
        self.project_specific_colorers[info.project_id].color_children_now_or_later(info.folder_id)


# There's no way to say "when this item is selected, show a green selection".
# But there is a way to say "when any item is selected, show a green selection".
# We just have to configure that whenever a different item is selected, lol
def update_tree_selection_color(tree: DirectoryTree, event: object = None) -> None:
    try:
        [selected_id] = tree.selection()
    except ValueError:  # nothing selected
        git_tags = []
    else:
        git_tags = [tag for tag in tree.item(selected_id, "tags") if tag.startswith("git_")]

    if git_tags:
        [tag] = git_tags
        color = tree.tag_configure(tag, "foreground")
        tree.tk.call(
            "ttk::style",
            "map",
            "DirectoryTreeGitStatus.Treeview",
            "-foreground",
            ["selected", color],
        )
    else:
        # use default colors
        tree.tk.eval("ttk::style map DirectoryTreeGitStatus.Treeview -foreground {}")


def sorting_key(tree: DirectoryTree, item_id: str) -> Any:
    [git_tag] = [t for t in tree.item(item_id, "tags") if t.startswith("git_")] or [None]
    return [
        "git_added",
        "git_modified",
        "git_mergeconflict",
        None,
        "git_untracked",
        "git_ignored",
    ].index(git_tag)


def setup() -> None:
    tree = get_directory_tree()
    tree.config(style="DirectoryTreeGitStatus.Treeview")

    main_colorer = TreeColorer(tree)
    tree.bind("<<RefreshBegins>>", main_colorer.start_status_coloring_for_all_projects, add=True)
    utils.bind_with_data(tree, "<<FolderRefreshed>>", main_colorer.color_child_items, add=True)

    tree.sorting_keys.insert(0, partial(sorting_key, tree))

    tree.bind("<<TreeviewSelect>>", partial(update_tree_selection_color, tree), add=True)
    update_tree_selection_color(tree)
    tree.bind("<<ThemeChanged>>", main_colorer.config_color_tags, add=True)
    main_colorer.config_color_tags()
