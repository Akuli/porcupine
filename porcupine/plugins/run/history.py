from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import dacite  # TODO: settings should do this automagically, but doesn't

from porcupine import settings, tabs

from . import common


@dataclasses.dataclass
class ExampleCommand:
    command: str
    windows_command: Optional[str] = None
    working_directory: str = "{folder_path}"
    external_terminal: bool = True


@dataclasses.dataclass
class _HistoryItem:
    command: common.Command
    last_use: float
    use_count: int


def add(command: common.Command) -> None:
    raw_history: list[dict[str, Any]] = settings.get("run_history", List[Any])
    history = [dacite.from_dict(_HistoryItem, raw_item) for raw_item in raw_history]

    old_use_count = 0
    for item in history:
        if (
            item.command.command_format == command.command_format
            and item.command.key_id == command.key_id
        ):
            old_use_count = item.use_count
            history.remove(item)
            break

    history.insert(
        0, _HistoryItem(command=command, last_use=time.time(), use_count=old_use_count + 1)
    )

    settings.set_(
        "run_history",
        [
            dataclasses.asdict(item)
            for index, item in enumerate(history)
            # Delete everything after first 50 commands if used only once
            # Delete everything after first 100 commands if used once or twice
            # etc
            if item.use_count > index / 50
        ],
    )


def get(tab: tabs.FileTab, project_path: Path, key_id: int) -> list[common.Command]:
    assert tab.path is not None

    raw_history: list[dict[str, Any]] = settings.get("run_history", List[Any]).copy()

    # backwards compat for between porcupine 0.98.2 and 0.99.0 (no released versions)
    for item in raw_history:
        if item.get("key_id", -1) not in range(4):
            item["key_id"] = 0

    typed_history = [dacite.from_dict(_HistoryItem, raw_item).command for raw_item in raw_history]
    commands = [command for command in typed_history if command.key_id == key_id]

    for example in tab.settings.get("example_commands", List[ExampleCommand]):
        if sys.platform == "win32" and example.windows_command is not None:
            command_format = example.windows_command
        else:
            command_format = example.command

        if command_format not in (item.command_format for item in commands):
            substitutions = common.get_substitutions(tab.path, project_path)
            commands.append(
                common.Command(
                    command_format=command_format,
                    command=common.format_command(command_format, substitutions),
                    cwd_format=example.working_directory,
                    cwd=str(common.format_cwd(example.working_directory, substitutions)),
                    external_terminal=example.external_terminal,
                    key_id=key_id,
                )
            )

    return commands
