"""Detects Python venvs (virtual environments).

To choose which venv to use, right-click it in directory tree and select
"Use this Python venv".
"""
from __future__ import annotations

import logging
import sys
import tkinter
from functools import partial
from pathlib import Path
from typing import Dict

import porcupine.plugins.directory_tree as dirtree
from porcupine import get_paned_window, settings, utils

log = logging.getLogger(__name__)
setup_after = ["directory_tree"]


def get_exe(venv: Path, name: str) -> Path:
    if sys.platform != "win32":
        if (venv / "bin" / name).exists():
            return venv / "bin" / name
    else:
        # TODO: which should be preferred, foo.bat or foo.exe?
        if (venv / "Scripts" / (name + ".bat")).exists():  # activate.bat
            return venv / "Scripts" / (name + ".bat")
        if (venv / "Scripts" / (name + ".exe")).exists():  # python.exe
            return venv / "Scripts" / (name + ".exe")

    return None


def is_venv(path: Path) -> bool:
    landmarks = [path / "pyvenv.cfg", get_exe(path, "python")]
    if sys.platform == "win32":
        landmarks.append(path / "Scripts" / "activate.bat")
    else:
        landmarks.append(path / "bin" / "activate")
    return all(landmark.exists() for landmark in landmarks)


def _find_venv(project_root: Path) -> Path | None:
    # TODO: how well is this all going to work with nested projects, and repos
    # that contain several subfolders with their own venvs?
    possible_envs = [path for path in project_root.glob("*env*") if is_venv(path)]
    if possible_envs:
        # Pick one consistently. Prefer shorter: env instead of env-old.
        return min(possible_envs, key=(lambda e: (len(str(e)), e)))
    log.debug(f"no virtualenvs found in {project_root}")
    return None


def get_venv(project_root: Path) -> Path | None:
    assert project_root.is_dir()
    custom_paths: Dict[str, str] = settings.get("python_venvs", Dict[str, str])

    if str(project_root) in custom_paths:
        from_settings = Path(custom_paths[str(project_root)])
        if is_venv(from_settings):
            return from_settings
        log.warning(f"Python venv is no longer valid: {from_settings}")

    result = _find_venv(project_root)
    if result is None:
        log.info(f"No venv found in {project_root}")
    else:
        log.info(f"Using {result} as venv of {project_root}")
        custom_paths[str(project_root)] = str(result)  # Do not automagically switch to new venvs
        settings.set_("python_venvs", custom_paths)  # custom_paths is copy
    return result


def set_venv(project_root: Path, venv: Path) -> None:
    assert is_venv(venv), venv
    custom_paths: dict[str, str] = settings.get("python_venvs", Dict[str, str])
    custom_paths[str(project_root)] = str(venv)
    settings.set_("python_venvs", custom_paths)  # custom_paths is copy
    log.info(f"Venv of {project_root} set to {venv}")


def _on_folder_refreshed(event: tkinter.Event[dirtree.DirectoryTree]) -> None:
    tree = event.widget
    info = event.data_class(dirtree.FolderRefreshed)

    # tkinter is lacking tag_remove and tag_add
    tree.tk.call(tree, "tag", "remove", "venv", tree.get_children(info.folder_id))

    venv = get_venv(dirtree.get_path(info.project_id))
    if venv is not None:
        venv_id = tree.get_id_from_path(venv, info.project_id)
        if venv_id is not None:
            tree.tk.call(tree, "tag", "add", "venv", venv_id)


def _on_right_click(event: tkinter.Event[dirtree.DirectoryTree]) -> str:
    tree = event.widget
    tree.tk.call("focus", tree)

    item: str = tree.identify_row(event.y)  # type: ignore[no-untyped-call]
    tree.set_the_selection_correctly(item)

    path = dirtree.get_path(item)
    project_root = dirtree.get_path(tree.find_project_id(item))
    if is_venv(path) and get_venv(project_root) != path:
        menu = tkinter.Menu(tearoff=False)
        menu.add_command(
            label="Use this Python venv",
            # No need to refresh when clicked, somehow already refreshes 4 times (lol)
            command=partial(set_venv, project_root, path),
        )
        menu.tk_popup(event.x_root, event.y_root)
        menu.bind("<Unmap>", (lambda event: menu.after_idle(menu.destroy)), add=True)
    return "break"


def setup() -> None:
    settings.add_option("python_venvs", {}, Dict[str, str])  # paths as strings, for json

    for widget in utils.get_children_recursively(get_paned_window()):
        if isinstance(widget, dirtree.DirectoryTree):
            utils.bind_with_data(widget, "<<FolderRefreshed>>", _on_folder_refreshed, add=True)
            widget.bind(
                "<Button-3>", _on_right_click, add=True
            )  # TODO: mac right click = button 2?
