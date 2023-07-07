from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable

from porcupine.tabs import FileTab

action_availability_callback = Callable[[], bool]


@dataclass(slots=True, frozen=True)
class Action:
    """Action that requires no context in the callback"""

    name: str
    description: str
    callback: Callable[..., None]
    availability_callbacks: list[action_availability_callback] | None = None


filetab_action_availability_callback = Callable[[FileTab], bool]


@dataclass(slots=True, frozen=True)
class FileTabAction:
    """Action that requires a FileTab to be provided to the callback"""

    name: str
    description: str
    callback: Callable[[FileTab], None]
    availability_callbacks: list[filetab_action_availability_callback] | None = None


path_action_availability_callback = Callable[[Path], bool]


@dataclass(slots=True, frozen=True)
class PathAction:
    """Action that requires a Path to be provided to the callback"""

    name: str
    description: str
    callback: Callable[[Path], None]
    file_compatible: bool = True
    directory_compatible: bool = False
    availability_callbacks: list[path_action_availability_callback] | None = None


ActionTypes = Action | FileTabAction | PathAction

_actions: dict[str, ActionTypes] = {}


def register_action(
    *,
    name: str,
    description: str,
    callback: Callable[..., None],
    availability_callbacks: list[action_availability_callback] | None = None,
) -> Action:
    if name in _actions:
        raise ValueError(f"Action with the name '{name}' already exists")
    action = Action(
        name=name,
        description=description,
        callback=callback,
        availability_callbacks=availability_callbacks,
    )
    _actions[name] = action
    return action


def register_filetab_action(
    *,
    name: str,
    description: str,
    callback: Callable[[FileTab], None],
    availability_callbacks: list[filetab_action_availability_callback] | None,
) -> FileTabAction:
    if name in _actions:
        raise ValueError(f"Action with the name '{name}' already exists")
    action = FileTabAction(
        name=name,
        description=description,
        callback=callback,
        availability_callbacks=availability_callbacks,
    )
    _actions[name] = action
    return action


def register_path_action(
    *,
    name: str,
    description: str,
    callback: Callable[[Path], None],
    file_compatible: bool = True,
    directory_compatible: bool = False,
    availability_callbacks: list[path_action_availability_callback] | None,
) -> PathAction:
    if name in _actions:
        raise ValueError(f"Action with the name '{name}' already exists")
    action = PathAction(
        name=name,
        description=description,
        callback=callback,
        file_compatible=file_compatible,
        directory_compatible=directory_compatible,
        availability_callbacks=availability_callbacks,
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
