from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path
from typing import List, Optional

import dacite

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
    use_count: int
    filetype_name: Optional[str]
    key_id: int


# not global variable because tests monkeypatch dirs after importing
def _get_path() -> Path:
    # config dir is better than cache dir https://github.com/davatorium/rofi/issues/769
    # Change the number after v when you make incompatible changes
    return Path(dirs.user_config_dir) / "run_history_v3
   .json"


def _load_json_file() -> list[_HistoryItem]:
    try:
        with _get_path().open("r", encoding="utf-8") as file:
            return [dacite.from_dict(_HistoryItem, raw_item) for raw_item in json.load(file)]
    except FileNotFoundError:
        return []


def add(tab: tabs.FileTab, command: common.Command, key_id: int) -> None:
    history_items = _load_json_file()

    old_use_count = 0
    for item in history_items:
        if (
            item.command.command_format == command.command_format
            and item.key_id == key_id
            and item.filetype_name == tab.settings.get("filetype_name", Optional[str])
        ):
            old_use_count = item.use_count
            history_items.remove(item)
            break

    history_items.insert(
        0,
        _HistoryItem(
            command=command,
            use_count=old_use_count + 1,
            key_id=key_id,
            filetype_name=tab.settings.get("filetype_name", Optional[str]),
        ),
    )

    with _get_path().open("w", encoding="utf-8") as file:
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


def _get_commands(
    tab: tabs.FileTab, project_path: Path, key_id: int, *, include_unmatching: bool = False
) -> list[common.Command]:
    assert tab.path is not None

    unmatching_commands = []
    commands = []
    for item in _load_json_file():
        if item.key_id == key_id and item.filetype_name == tab.settings.get(
            "filetype_name", Optional[str]
        ):
            commands.append(item.command)
        else:
            unmatching_commands.append(item.command)

    for example in tab.settings.get("example_commands", List[ExampleCommand]):
        if sys.platform == "win32" and example.windows_command is not None:
            command_format = example.windows_command
        elif sys.platform == "darwin" and example.macos_command is not None:
            command_format = example.macos_command
        else:
            command_format = example.command

        if command_format not in (item.command_format for item in commands):
            commands.append(
                common.Command(
                    command_format=command_format,
                    cwd_format=example.working_directory,
                    external_terminal=example.external_terminal,
                    substitutions=common.get_substitutions(tab.path, project_path),
                )
            )

    if include_unmatching:
        commands.extend(unmatching_commands)
    return commands


def get_command_to_repeat(
    tab: tabs.FileTab, project_path: Path, key_id: int
) -> common.Command | None:
    assert tab.path is not None

    alternatives = _get_commands(tab, project_path, key_id)
    if alternatives:
        command = copy.copy(alternatives[0])
        command.substitutions = common.get_substitutions(tab.path, project_path)
        return command
    return None


def get_commands_to_suggest(
    tab: tabs.FileTab, project_path: Path, key_id: int
) -> list[common.Command]:
    return _get_commands(tab, project_path, key_id, include_unmatching=True)
