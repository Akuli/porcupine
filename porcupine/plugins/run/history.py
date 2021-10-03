from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

from porcupine import settings, tabs, utils


@dataclass
class ExampleCommand:
    command: str
    windows_command: Optional[str] = None
    working_directory: str = "{folder_path}"
    external_terminal: bool = True


# dict because must be json safe
class Command(TypedDict):
    command_format: str
    command: str
    cwd_format: str
    cwd: str  # not pathlib.Path because must be json safe
    external_terminal: bool


class HistoryItem(TypedDict):
    command: Command
    last_use: float
    use_count: int


def get_substitutions(file_path: Path, project_path: Path) -> dict[str, str]:
    return {
        "file_stem": file_path.stem,
        "file_name": file_path.name,
        "file_path": str(file_path),
        "folder_name": file_path.parent.name,
        "folder_path": str(file_path.parent),
        "project_name": project_path.name,
        "project_path": str(project_path),
    }


def format_cwd(cwd_format: str, substitutions: dict[str, str]) -> Path:
    return Path(cwd_format.format(**substitutions))


def format_command(command_format: str, substitutions: dict[str, str]) -> str:
    return command_format.format(
        **{name: utils.quote(value) for name, value in substitutions.items()}
    )


def add(command: Command) -> None:
    history: list[HistoryItem] = settings.get("run_history", List[Any])

    old_use_count = 0
    for item in history:
        if item["command"]["command_format"] == command["command_format"]:
            old_use_count = item["use_count"]
            history.remove(item)
            break

    history.insert(
        0, {"command": command.copy(), "last_use": time.time(), "use_count": old_use_count + 1}
    )

    settings.set_(
        "run_history",
        [
            item
            for index, item in enumerate(history)
            # Delete everything after first 50 commands if used only once
            # Delete everything after first 100 commands if used once or twice
            # etc
            if item["use_count"] > index / 50
        ],
    )


def get(tab: tabs.FileTab, project_path: Path) -> list[HistoryItem]:
    assert tab.path is not None

    result: list[HistoryItem] = settings.get("run_history", List[Any]).copy()
    for example in tab.settings.get("example_commands", List[ExampleCommand]):
        if sys.platform == "win32" and example.windows_command is not None:
            command = example.windows_command
        else:
            command = example.command

        if command not in (item["command"]["command_format"] for item in result):
            substitutions = get_substitutions(tab.path, project_path)
            result.append(
                {
                    "command": {
                        "command_format": command,
                        "command": format_command(command, substitutions),
                        "cwd_format": example.working_directory,
                        "cwd": str(format_cwd(example.working_directory, substitutions)),
                        "external_terminal": example.external_terminal,
                    },
                    "last_use": 0,
                    "use_count": 0,
                }
            )
    return result
