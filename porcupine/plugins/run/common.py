from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Dict, List, Optional

from porcupine import tabs, utils


@dataclasses.dataclass
class Command:
    command_format: str
    cwd_format: str
    external_terminal: bool
    substitutions: dict[str, str]

    def format_cwd(self) -> Path:
        return Path(self.cwd_format.format(**self.substitutions))

    def format_command(self) -> str:
        return self.command_format.format(
            **{name: utils.quote(value) for name, value in self.substitutions.items()}
        )


@dataclasses.dataclass
class ExampleCommand:
    command: str
    windows_command: Optional[str] = None
    macos_command: Optional[str] = None
    working_directory: str = "{folder_path}"
    external_terminal: bool = True


class Context:
    def __init__(self, tab: tabs.FileTab, key_id: int):
        assert tab.path is not None
        self.file_path = tab.path
        self.project_path = utils.find_project_root(tab.path)
        self.key_id = key_id  # with default bindings: 0 = F5, 1 = F6, 2 = F7, 3 = F8
        self.filetype_name: str | None = tab.settings.get("filetype_name", Optional[str])
        self.example_commands: list[ExampleCommand] = tab.settings.get(
            "example_commands", list[ExampleCommand]
        )

    def get_substitutions(self) -> dict[str, str]:
        return {
            "file_stem": self.file_path.stem,
            "file_name": self.file_path.name,
            "file_path": str(self.file_path),
            "folder_name": self.file_path.parent.name,
            "folder_path": str(self.file_path.parent),
            "project_name": self.project_path.name,
            "project_path": str(self.project_path),
        }


def prepare_env() -> dict[str, str]:
    env = dict(os.environ)

    # If Porcupine is running within a virtualenv, ignore it
    if "VIRTUAL_ENV" in env and "PATH" in env:
        # os.pathsep = ":"
        # os.sep = "/"
        porcu_venv = env.pop("VIRTUAL_ENV")
        env["PATH"] = os.pathsep.join(
            p for p in env["PATH"].split(os.pathsep) if not p.startswith(porcu_venv + os.sep)
        )

    return env
