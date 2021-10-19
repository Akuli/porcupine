from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Dict, List, Optional

from porcupine import tabs, utils


@dataclasses.dataclass
class Command:
    command_format: str
    cwd_format: str
    external_terminal: bool
    substitutions: Dict[str, str]

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


@dataclasses.dataclass
class Context:
    file_path: Path
    project_path: Path
    key_id: int
    filetype_name: str | None
    example_commands: list[ExampleCommand]

    @staticmethod
    def from_tab(tab: tabs.FileTab, key_id: int) -> Context:
        assert tab.path is not None
        return Context(
            file_path=tab.path,
            project_path=utils.find_project_root(tab.path),
            key_id=key_id,
            filetype_name=tab.settings.get("filetype_name", Optional[str]),
            example_commands=tab.settings.get("example_commands", List[ExampleCommand]),
        )


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
