from __future__ import annotations

import dataclasses
import os
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from porcupine import tabs, utils
from porcupine.settings import global_settings


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


class Context:
    def __init__(self, tab: tabs.FileTab, key_id: int) -> None:
        assert tab.path is not None
        self.file_path = tab.path
        self.project_path = utils.find_project_root(tab.path)
        self.key_id = key_id  # with default bindings: 0 = F5, 1 = F6, 2 = F7, 3 = F8
        self.filetype_name: str | None = tab.settings.get("filetype_name", Optional[str])
        self.example_commands: list[ExampleCommand] = tab.settings.get(
            "example_commands", List[ExampleCommand]
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


def mem_limit_to_string(limit: int) -> str:
    if limit >= 1000 * 1000 * 1000:
        number = limit / (1000 * 1000 * 1000)
        suffix = "GB"
    elif limit >= 1000 * 1000:
        number = limit / (1000 * 1000)
        suffix = "MB"
    elif limit >= 1000:
        number = limit / 1000
        suffix = "KB"
    else:
        number = limit
        suffix = "B"

    # Show 2GB instead of 2.0GB
    if number == int(number):
        number = int(number)

    return str(number) + suffix


def string_to_mem_limit(string: str) -> int | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMG]?)B?", string.replace(" ", "").upper())
    if match is None:
        return None

    number_as_string, suffix = match.groups()
    number = float(number_as_string)
    if suffix == "":
        limit = round(number)
    elif suffix == "K":
        limit = round(1000 * number)
    elif suffix == "M":
        limit = round(1000 * 1000 * number)
    elif suffix == "G":
        limit = round(1000 * 1000 * 1000 * number)
    else:
        raise NotImplementedError

    # Ban limits smaller than 10MB. Python needs about 17MB to start.
    if limit < 10 * 1000 * 1000:
        return None
    return limit


# If statements must be outside the function definition because of mypy bugs
if sys.platform == "win32":

    def create_memory_limit_callback() -> Callable[[], None]:
        raise NotImplementedError

else:
    import resource

    def create_memory_limit_callback() -> Callable[[], None]:
        if not global_settings.get("run_mem_limit_enabled", bool):
            return lambda: None

        limit = global_settings.get("run_mem_limit_value", int)
        limit_string = mem_limit_to_string(limit)

        def callback() -> None:
            try:
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            except Exception as e:
                # Avoid using anything that acquires IO locks.
                # Still not great, because the GIL could deadlock. See warning in docs.
                message = f"Limiting memory usage to {limit_string} failed: {e}\r\n"
                os.write(2, message.encode("utf-8"))

        return callback
