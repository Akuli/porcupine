"""Adds "Hide this project" button when right-clicking a project in the directory tree."""
from __future__ import annotations

import tkinter

from porcupine.plugins.directory_tree import DirectoryTree, get_directory_tree

setup_after = ["directory_tree"]


def add_hide_option(event: tkinter.Event[DirectoryTree]) -> None:
    tree: DirectoryTree = event.widget
    [project_id] = tree.selection()
    if not project_id.startswith("project:"):
        return

    def on_click() -> None:
        tree.delete(project_id)
        tree.save_project_list()

    tree.contextmenu.add_command(
        label="Hide this project",
        command=on_click,
        state="disabled" if tree.project_has_opened_tabs(project_id) else "normal",
    )


def setup() -> None:
    get_directory_tree().bind("<<PopulateContextMenu>>", add_hide_option, add=True)
