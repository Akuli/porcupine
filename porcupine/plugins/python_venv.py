"""Detects Python venvs (virtual environments).

To choose which venv to use, right-click it in directory tree and select
"Use this venv".
"""
from __future__ import annotations

import logging
import pathlib
import sys
from typing import Dict

from cachetools.func import ttl_cache

from porcupine import settings

log = logging.getLogger(__name__)


def is_venv(path: pathlib.Path) -> bool:
    landmarks = [path / "pyvenv.cfg"]
    if sys.platform == "win32":
        landmarks.append(path / "Scripts" / "activate.bat")
        landmarks.append(path / "Scripts" / "python.exe")
    else:
        landmarks.append(path / "bin" / "activate")
        landmarks.append(path / "bin" / "python3")

    return all(landmark.exists() for landmark in landmarks)


def _find_venv(project_root: pathlib.Path) -> pathlib.Path | None:
    # TODO: how well is this all going to work with nested projects, and repos
    # that contain several subfolders with their own venvs?
    possible_envs = [path for path in project_root.glob("*env*") if is_venv(path)]
    if possible_envs:
        # Pick one consistently. Prefer shorter: env instead of env-old.
        return min(possible_envs, key=(lambda e: (len(str(e)), e)))
    log.debug(f"no virtualenvs found in {project_root}")
    return None


# mypy+decorator weirdness
def get_venv(project_root: pathlib.Path) -> pathlib.Path | None:
    ...


# TODO: cache is a bit of a hack. Directory tree calls this too much.
# Focus Porcupine when running with --verbose:
#
# - Before cache, porcupine project open:
#       porcupine.plugins.directory_tree DEBUG: refreshing done in 268ms
#
# - After adding cache:
#       porcupine.plugins.directory_tree DEBUG: refreshing done in 153ms
#       porcupine.plugins.directory_tree DEBUG: refreshing done in 149ms
#   Yes, it can run twice. That's another perf problem.
@ttl_cache(ttl=0.100, maxsize=10)  # noqa  # type: ignore
def get_venv(project_root: pathlib.Path) -> pathlib.Path | None:
    assert project_root.is_dir()
    custom_paths: Dict[str, str] = settings.get("python_venvs", Dict[str, str])

    if str(project_root) in custom_paths:
        from_settings = pathlib.Path(custom_paths[str(project_root)])
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


def set_venv(project_root: pathlib.Path, venv: pathlib.Path) -> None:
    assert is_venv(venv), venv
    custom_paths: dict[str, str] = settings.get("python_venvs", Dict[str, str])
    custom_paths[str(project_root)] = str(venv)
    settings.set_("python_venvs", custom_paths)  # custom_paths is copy
    log.info(f"Venv of {project_root} set to {venv}")


def setup() -> None:
    settings.add_option("python_venvs", {}, Dict[str, str])  # paths as strings, for json
