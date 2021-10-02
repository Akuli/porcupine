from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional

from typing_extensions import TypedDict

from porcupine import settings, tabs

if TYPE_CHECKING:
    from .dialog import CommandSpec


@dataclass
class ExampleCommand:
    command: str
    windows_command: Optional[str] = None
    working_directory: str = "{folder_path}"
    external_terminal: bool = True


class HistoryItem(TypedDict):
    command_format: str
    cwd_format: str
    external_terminal: bool
    last_use: float  # time.time() value, not datetime because json safe
    use_count: int


def add(spec: CommandSpec) -> None:
    history: list[HistoryItem] = settings.get("run_history", List[Any])

    old_use_count = 0
    for item in history:
        if item["command_format"] == spec.command_format:
            old_use_count = item["use_count"]
            history.remove(item)
            break

    history.insert(
        0,
        {
            "command_format": spec.command_format,
            "cwd_format": spec.cwd_format,
            "external_terminal": spec.external_terminal,
            "use_count": old_use_count + 1,
            "last_use": time.time(),
        },
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


def get(tab: tabs.FileTab) -> list[HistoryItem]:
    result: list[HistoryItem] = settings.get("run_history", List[Any]).copy()
    for example in tab.settings.get("example_commands", List[ExampleCommand]):
        if sys.platform == "win32" and example.windows_command is not None:
            command = example.windows_command
        else:
            command = example.command

        if command not in (item["command_format"] for item in result):
            result.append(
                {
                    "command_format": command,
                    "cwd_format": example.working_directory,
                    "external_terminal": example.external_terminal,
                    "last_use": 0,
                    "use_count": 0,
                }
            )
    return result
