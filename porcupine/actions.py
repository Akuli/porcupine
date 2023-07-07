from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, Union

from porcupine.tabs import FileTab

action_availability_callback = Callable[[], bool]


@dataclass(frozen=True)
class BareAction:
    """Action that requires no context in the callback"""

    name: str
    description: str
    callback: Callable[[], None]
    availability_callback: action_availability_callback


filetab_action_availability_callback = Callable[[FileTab], bool]


@dataclass(frozen=True)
class FileTabAction:
    """Action that requires a FileTab to be provided to the callback"""

    name: str
    description: str
    callback: Callable[[FileTab], None]
    availability_callback: filetab_action_availability_callback


path_action_availability_callback = Callable[[Path], bool]


@dataclass(frozen=True)
class PathAction:
    """Action that requires a Path to be provided to the callback"""

    name: str
    description: str
    callback: Callable[[Path], None]
    availability_callback: path_action_availability_callback


Action = Union[BareAction, FileTabAction, PathAction]

_actions: dict[str, Action] = {}


def register_action(
    *,
    name: str,
    description: str,
    callback: Callable[..., None],
    availability_callback: action_availability_callback = lambda: True,
) -> BareAction:
    if name in _actions:
        raise ValueError(f"Action with the name '{name}' already exists")
    action = BareAction(
        name=name,
        description=description,
        callback=callback,
        availability_callback=availability_callback,
    )
    _actions[name] = action
    return action


def register_filetab_action(
    *,
    name: str,
    description: str,
    callback: Callable[[FileTab], None],
    availability_callback: filetab_action_availability_callback = lambda tab: True,
) -> FileTabAction:
    if name in _actions:
        raise ValueError(f"Action with the name '{name}' already exists")
    action = FileTabAction(
        name=name,
        description=description,
        callback=callback,
        availability_callback=availability_callback,
    )
    _actions[name] = action
    return action


def register_path_action(
    *,
    name: str,
    description: str,
    callback: Callable[[Path], None],
    availability_callback: path_action_availability_callback = lambda path: True,
) -> PathAction:
    if name in _actions:
        raise ValueError(f"Action with the name '{name}' already exists")
    action = PathAction(
        name=name,
        description=description,
        callback=callback,
        availability_callback=availability_callback,
    )
    _actions[name] = action
    return action


def filetype_availability(filetypes: list[str]) -> Callable[[FileTab | Path], bool]:
    def _filetype_availability(filetypes: list[str], context: FileTab | Path) -> bool:
        if isinstance(context, FileTab):
            tab = context
            if tab.settings.get("filetype_name", object) in filetypes:
                return True
            return False

        if isinstance(context, Path):
            path = context

            if not path.exists():
                raise RuntimeError(f"{path} does not exist.")
            if path.is_dir():
                raise RuntimeError(
                    f"{path} is a directory - an action consumer registered this action incorrectly"
                )
            if not path.is_file():
                raise RuntimeError(f"{path} is not a file")

            # return True if get_filetype_from_path(path) in filetypes else False
            raise NotImplementedError  # TODO: there is a way to do this already right?

        raise RuntimeError("wrong context passed")

    return partial(_filetype_availability, filetypes)
