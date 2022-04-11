"""Detects Python venvs (virtual environments).

To choose which venv to use, right-click it in directory tree and select
"Use this Python venv".
"""
from __future__ import annotations

import logging
import shutil
import sys
import tkinter
from pathlib import Path
from typing import Any, Dict, Optional, cast

import porcupine.plugins.directory_tree as dirtree
from porcupine import images, settings, utils
from porcupine.settings import global_settings

log = logging.getLogger(__name__)
setup_after = ["directory_tree"]


def is_venv(path: Path) -> bool:
    landmarks = [path / "pyvenv.cfg"]
    if sys.platform == "win32":
        landmarks.append(path / "Scripts" / "python.exe")
        landmarks.append(path / "Scripts" / "activate.bat")
    else:
        landmarks.append(path / "bin" / "python3")
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


def set_venv(project_root: Path, venv: Path | None) -> None:
    if venv is not None:
        assert is_venv(venv), venv

    custom_paths: dict[str, str | None] = global_settings.get(
        "python_venvs", Dict[str, Optional[str]]
    )
    custom_paths[str(project_root)] = None if venv is None else str(venv)
    global_settings.set("python_venvs", custom_paths)  # custom_paths is copy
    log.info(f"venv of {project_root} set to {venv}")


def get_venv(project_root: Path) -> Path | None:
    assert project_root.is_dir()
    custom_paths: dict[str, str | None] = global_settings.get(
        "python_venvs", Dict[str, Optional[str]]
    )

    if str(project_root) in custom_paths:
        path_string = custom_paths[str(project_root)]
        if path_string is None:
            log.info(f"user has unselected venv for {project_root}")
            return None

        from_settings = Path(path_string)
        if is_venv(from_settings):
            return from_settings

        log.warning(f"Python venv is no longer valid: {from_settings}")
        del custom_paths[str(project_root)]
        global_settings.set("python_venvs", custom_paths)  # custom_paths is copy

    result = _find_venv(project_root)
    if result is None:
        log.info(f"No venv found in {project_root}")
    else:
        set_venv(project_root, result)
    return result


# This doesn't use Porcupine's python, unless py or python3 points to it
def find_python(project_root: Path | None) -> Path | None:
    if project_root is not None:
        venv = get_venv(project_root)
        if venv is not None:
            log.info(f"Using python from venv: {venv}")
            if sys.platform == "win32":
                return venv / "Scripts" / "python.exe"
            else:
                return venv / "bin" / "python"

    if sys.platform == "win32":
        log.info("No venv found, using py")
        result = shutil.which("py")
    else:
        log.info("No venv found, using python3")
        result = shutil.which("python3")

    if result is None:
        log.warning("no Python found")
        return None
    return Path(result)


def _on_folder_refreshed(event: utils.EventWithData) -> None:
    tree = event.widget
    assert isinstance(tree, dirtree.DirectoryTree)
    info = event.data_class(dirtree.FolderRefreshed)

    # tkinter is lacking tag_remove and tag_add
    tree.tk.call(tree, "tag", "remove", "venv", tree.get_children(info.folder_id))

    venv = get_venv(dirtree.get_path(info.project_id))
    if venv is not None:
        venv_id = tree.get_id_from_path(venv, info.project_id)
        if venv_id is not None:
            tree.tk.call(tree, "tag", "add", "venv", [venv_id])


def _populate_menu(event: tkinter.Event[dirtree.DirectoryTree]) -> None:
    tree: dirtree.DirectoryTree = event.widget
    [item] = tree.selection()
    path = dirtree.get_path(item)
    project_root = dirtree.get_path(tree.find_project_id(item))
    if not is_venv(path):
        return

    def on_change(*junk: object) -> None:
        set_venv(project_root, path if var.get() else None)
        tree.refresh()  # needed on windows

    var = tkinter.BooleanVar(value=(get_venv(project_root) == path))
    var.trace_add("write", on_change)
    cast(Any, tree.contextmenu).garbage_collection_is_lol = var

    tree.contextmenu.add_checkbutton(label="Use this Python venv", variable=var)


def setup() -> None:
    # paths as strings, for json
    global_settings.add_option(
        "python_venvs", {}, Dict[str, Optional[str]]
    )  

    try:
        tree = dirtree.get_directory_tree()
    except RuntimeError:
        # directory tree plugin disabled
        pass
    else:
        tree.tag_configure("venv", image=images.get("venv"))
        utils.bind_with_data(tree, "<<FolderRefreshed>>", _on_folder_refreshed, add=True)
        tree.bind("<<PopulateContextMenu>>", _populate_menu, add=True)
