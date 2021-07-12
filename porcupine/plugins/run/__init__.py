"""Compile, run and lint files."""
from __future__ import annotations

import dataclasses
import logging
import os
import pathlib
import sys
from functools import partial
from typing import Callable

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

from porcupine import get_tab_manager, menubar, tabs, utils
from porcupine.plugins import python_venv

from . import no_terminal, terminal

log = logging.getLogger(__name__)


@dataclasses.dataclass
class CommandsConfig:
    compile: str = ""
    run: str = ""
    lint: str = ""


def has_command(
    which_command: Literal["compile", "run", "compilerun", "lint"], tab: tabs.Tab | None
) -> bool:
    if not isinstance(tab, tabs.FileTab):
        return False

    try:
        config = tab.settings.get("commands", CommandsConfig)
    except KeyError:
        # Happens when opening new tab, option will be added and will be called again soon
        return False

    if which_command == "compilerun":
        return bool(config.compile) and bool(config.run)
    return bool(getattr(config, which_command))


def get_command(
    tab: tabs.FileTab, which_command: Literal["compile", "run", "lint"], basename: str
) -> list[str]:
    assert os.sep not in basename, f"{basename!r} is not a basename"

    commands = tab.settings.get("commands", CommandsConfig)
    assert isinstance(commands, CommandsConfig)
    template = getattr(commands, which_command)
    assert template.strip(), (commands, which_command)

    exts = "".join(pathlib.Path(basename).suffixes)
    no_ext = pathlib.Path(basename).stem
    return utils.format_command(
        template,
        {
            "file": basename,
            "no_ext": no_ext,
            "no_exts": basename[: -len(exts)] if exts else basename,
            "python": python_venv.find_python(
                None if tab.path is None else utils.find_project_root(tab.path)
            ),
            "exe": f"{no_ext}.exe" if sys.platform == "win32" else f"./{no_ext}",
        },
    )


def do_something(
    something: Literal["compile", "run", "compilerun", "lint"], tab: tabs.FileTab
) -> None:
    tab.save()
    if tab.path is None:
        # user cancelled a save as dialog
        return

    workingdir = tab.path.parent
    basename = tab.path.name

    if something == "run":
        terminal.run_command(workingdir, get_command(tab, "run", basename))
    elif something == "compilerun":
        compile_command = get_command(tab, "compile", basename)
        run_command = get_command(tab, "run", basename)
        no_terminal.run_command(
            workingdir, compile_command, partial(terminal.run_command, workingdir, run_command)
        )
    else:
        no_terminal.run_command(workingdir, get_command(tab, something, basename))


def on_new_filetab(call_when_commands_change: list[Callable[..., None]], tab: tabs.FileTab) -> None:
    tab.settings.add_option("commands", CommandsConfig())
    for func in call_when_commands_change:
        tab.bind("<<TabSettingChanged:commands>>", func, add=True)
        func()


def setup() -> None:
    call_when_commands_change: list[Callable[..., None]] = []
    get_tab_manager().add_filetab_callback(partial(on_new_filetab, call_when_commands_change))

    for name, command in [
        ("Compile", "compile"),
        ("Run", "run"),
        ("Compile and Run", "compilerun"),
        ("Lint", "lint"),
    ]:
        menubar.add_filetab_command(f"Run/{name}", partial(do_something, command))
        call_when_commands_change.append(
            menubar.set_enabled_based_on_tab(f"Run/{name}", partial(has_command, command))
        )
