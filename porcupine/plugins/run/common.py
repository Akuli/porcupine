from __future__ import annotations

import dataclasses
from pathlib import Path

from porcupine import utils


@dataclasses.dataclass
class Command:
    command_format: str
    command: str
    cwd_format: str
    cwd: str  # not pathlib.Path because must be json safe
    external_terminal: bool
    key_id: int  # with default bindings: 0 = F5, 1 = F6, 2 = F7, 3 = F8


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


ASK_EVENTS = [
    "<<Run:AskAndRun0>>",
    "<<Run:AskAndRun1>>",
    "<<Run:AskAndRun2>>",
    "<<Run:AskAndRun3>>",
]
REPEAT_EVENTS = [
    "<<Run:Repeat0>>",
    "<<Run:Repeat1>>",
    "<<Run:Repeat2>>",
    "<<Run:Repeat3>>",
]
