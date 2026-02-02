from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Union

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
        raise ValueError(f"Action with the name {name!r} already exists")
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
        raise ValueError(f"Action with the name {name!r} already exists")
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
        raise ValueError(f"Action with the name {name!r} already exists")
    action = PathAction(
        name=name,
        description=description,
        callback=callback,
        availability_callback=availability_callback,
    )
    _actions[name] = action
    return action


def get_action(name: str) -> Action | None:
    return _actions.get(name)


def get_all_actions() -> dict[str, Action]:
    return _actions.copy()


# Availability Helpers


def filetype_is(filetypes: str | list[str]) -> Callable[[FileTab], bool]:
    def _filetype_is(filetypes: list[str], tab: FileTab) -> bool:
        try:
            filetype = tab.settings.get("filetype_name", object)
        except KeyError:
            # don't ask me why a `get` method can raise a KeyError :p
            return False

        return filetype in filetypes

    if isinstance(filetypes, str):
        filetypes = [filetypes]

    return partial(_filetype_is, filetypes)
