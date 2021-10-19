from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Dict

from porcupine import utils


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

    def get_extension(self) -> str:
        return get_extension(Path(self.substitutions["file_path"]))

# Not same as path.suffix, because we want to distinguish files
# that have no suffix (e.g. 'Makefile')
def get_extension(path: Path) -> str:
    return path.name.split(".")[-1]


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
