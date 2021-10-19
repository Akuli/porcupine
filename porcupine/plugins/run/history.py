from __future__ import annotations

import copy
import dataclasses
import json
import sys
from pathlib import Path
from typing import Optional

import dacite

from porcupine import dirs

from . import common


@dataclasses.dataclass
class _HistoryItem:
    command: common.Command
    use_count: int
    filetype_name: Optional[str]
    key_id: int  # with default bindings: 0 = F5, 1 = F6, 2 = F7, 3 = F8


# not global variable because tests monkeypatch dirs after importing
def _get_path() -> Path:
    # config dir is better than cache dir https://github.com/davatorium/rofi/issues/769
    # Change the number after v when you make incompatible changes
    return Path(dirs.user_config_dir) / "run_history_v3.json"


def _load_json_file() -> list[_HistoryItem]:
    try:
        with _get_path().open("r", encoding="utf-8") as file:
            return [dacite.from_dict(_HistoryItem, raw_item) for raw_item in json.load(file)]
    except FileNotFoundError:
        return []


def add(ctx: common.Context, command: common.Command) -> None:
    history_items = _load_json_file()

    old_use_count = 0
    for item in history_items:
        if (
            item.command.command_format == command.command_format
            and item.key_id == ctx.key_id
            and item.filetype_name == ctx.filetype_name
        ):
            old_use_count = item.use_count
            history_items.remove(item)
            break

    history_items.insert(
        0,
        _HistoryItem(
            command=command,
            use_count=old_use_count + 1,
            key_id=ctx.key_id,
            filetype_name=ctx.filetype_name,
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


def _get_commands(ctx: common.Context, *, include_unmatching: bool = False) -> list[common.Command]:
    unmatching_commands = []
    commands = []
    for item in _load_json_file():
        if item.key_id == ctx.key_id and item.filetype_name == ctx.filetype_name:
            commands.append(item.command)
        else:
            unmatching_commands.append(item.command)

    for example in ctx.example_commands:
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
                    substitutions=common.get_substitutions(ctx.file_path, ctx.project_path),
                )
            )

    if include_unmatching:
        commands.extend(unmatching_commands)
    return commands


def get_command_to_repeat(ctx: common.Context) -> common.Command | None:
    alternatives = _get_commands(ctx)
    if alternatives:
        command = copy.copy(alternatives[0])
        command.substitutions = common.get_substitutions(ctx.file_path, ctx.project_path)
        return command
    return None


def get_commands_to_suggest(ctx: common.Context) -> list[common.Command]:
    return _get_commands(ctx, include_unmatching=True)
