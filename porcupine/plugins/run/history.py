from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import dacite  # TODO: settings should do this automagically, but doesn't

from porcupine import dirs, tabs

from . import common


@dataclasses.dataclass
class ExampleCommand:
    command: str
    windows_command: Optional[str] = None
    macos_command: Optional[str] = None
    working_directory: str = "{folder_path}"
    external_terminal: bool = True


@dataclasses.dataclass
class _HistoryItem:
    command: common.Command
    last_use: float
    use_count: int


def _load_items() -> List[_HistoryItem]:
    try:
        with (Path(dirs.user_config_dir) / "run_history.json").open("r", encoding="utf-8") as file:
            return [dacite.from_dict(_HistoryItem, raw_item) for raw_item in json.load(file)]
    except FileNotFoundError:
        return []


def add(command: common.Command) -> None:
    history_items = _load_items()

    old_use_count = 0
    for item in history_items:
        if (
            item.command.command_format == command.command_format
            and item.command.key_id == command.key_id
        ):
            old_use_count = item.use_count
            history_items.remove(item)
            break

    history_items.insert(
        0, _HistoryItem(command=command, last_use=time.time(), use_count=old_use_count + 1)
    )

    with (Path(dirs.user_config_dir) / "run_history.json").open("w", encoding="utf-8") as file:
        json.dump(
            [
                dataclasses.asdict(item)
                for index, item in enumerate(history_items)
                # Delete everything after first 50 commands if used only once
                # Delete everything after first 100 commands if used once or twice
                # etc
                if item.use_count > index / 50
            ],
            file,
            indent=4,
        )
        file.write("\n")


def get(tab: tabs.FileTab, project_path: Path, key_id: int) -> list[common.Command]:
    assert tab.path is not None
    commands = [item.command for item in _load_items() if item.command.key_id == key_id]

    for example in tab.settings.get("example_commands", List[ExampleCommand]):
        if sys.platform == "win32" and example.windows_command is not None:
            command_format = example.windows_command
        elif sys.platform == "darwin" and example.macos_command is not None:
            command_format = example.macos_command
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
