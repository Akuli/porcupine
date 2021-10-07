from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

import dacite  # TODO: settings should do this automagically, but doesn't

from porcupine import settings, tabs, utils


@dataclasses.dataclass
class ExampleCommand:
    command: str
    windows_command: Optional[str] = None
    working_directory: str = "{folder_path}"
    external_terminal: bool = True


@dataclasses.dataclass
class Command:
    command_format: str
    command: str
    cwd_format: str
    cwd: str  # not pathlib.Path because must be json safe
    external_terminal: bool
    key_id: int = 1  # 1 = F5, 2 = F6, 3 = F7, 4 = F8


@dataclasses.dataclass
class _HistoryItem:
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
    raw_history: list[dict[str, Any]] = settings.get("run_history", List[Any])
    history = [dacite.from_dict(_HistoryItem, raw_item) for raw_item in raw_history]

    old_use_count = 0
    for item in history:
        if item.command.command_format == command.command_format:
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


def get(tab: tabs.FileTab, project_path: Path, key_id: int) -> list[Command]:
    assert tab.path is not None

    raw_history: list[dict[str, Any]] = settings.get("run_history", List[Any]).copy()

    # backwards compat for between porcupine 0.98.2 and 0.99.0 (no released versions)
    for item in raw_history:
        item.setdefault("key_id", 1)

    typed_history = [dacite.from_dict(_HistoryItem, raw_item).command for raw_item in raw_history]
    commands = [command for command in typed_history if command.key_id == key_id]

    examples = tab.settings.get("example_commands", List[ExampleCommand])

    # key_id = 1: first example command goes first
    # key_id = 2: second example command goes first, first example goes last
    # key_id = 3: third example command goes first
    # key_id = 4: fourth example command goes first
    #
    # This way you can by default press F5 to run first example, F6 to run
    # second, etc, but all examples will show up in autocompletions.
    assert key_id >= 1
    examples = examples[key_id - 1:] + examples[:key_id - 1]

    for example in examples:
        if sys.platform == "win32" and example.windows_command is not None:
            command_format = example.windows_command
        else:
            command_format = example.command

        if command_format not in (item.command_format for item in commands):
            substitutions = get_substitutions(tab.path, project_path)
            commands.append(
                Command(
                    command_format=command_format,
                    command=format_command(command_format, substitutions),
                    cwd_format=example.working_directory,
                    cwd=str(format_cwd(example.working_directory, substitutions)),
                    external_terminal=example.external_terminal,
                    key_id=key_id,
                )
            )

    return commands
