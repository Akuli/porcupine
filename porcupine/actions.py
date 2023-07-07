from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Union

from porcupine.tabs import FileTab


@dataclass(frozen=True)
class BareAction:
    """Action that requires no context in the callback"""

    name: str
    description: str
    callback: Callable[[], None]
    availability_callback: Callable[[], bool]


@dataclass(frozen=True)
class FileTabAction:
    """Action that requires a FileTab to be provided to the callback"""

    name: str
    description: str
    callback: Callable[[FileTab], None]
    availability_callback: Callable[[FileTab], bool]


@dataclass(frozen=True)
class PathAction:
    """Action that requires a Path to be provided to the callback"""

    name: str
    description: str
    callback: Callable[[Path], None]
    availability_callback: Callable[[Path], bool]


Action = Union[BareAction, FileTabAction, PathAction]

_actions: dict[str, Action] = {}


def register_bare_action(
    *,
    name: str,
    description: str,
    callback: Callable[..., None],
    availability_callback: Callable[[], bool] = lambda: True,
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
    availability_callback: Callable[[FileTab], bool] = lambda tab: True,
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
    availability_callback: Callable[[Path], bool] = lambda path: True,
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


def query_actions(name: str) -> Action | None:
    return _actions.get(name)


def get_all_actions() -> dict[str, Action]:
    return _actions.copy()
