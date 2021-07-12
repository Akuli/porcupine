"""Compile, run and lint files."""
from __future__ import annotations

import dataclasses
import logging
import os
import pathlib
import sys
from functools import partial

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


def get_command(
    tab: tabs.FileTab, which_command: Literal["compile", "run", "lint"], basename: str
) -> list[str] | None:
    assert os.sep not in basename, f"{basename!r} is not a basename"

    commands = tab.settings.get("commands", CommandsConfig)
    assert isinstance(commands, CommandsConfig)
    template = getattr(commands, which_command)
    if not template.strip():
        return None

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
        command = get_command(tab, "run", basename)
        if command is not None:
            terminal.run_command(workingdir, command)

    elif something == "compilerun":

        def run_after_compile() -> None:
            command = get_command(tab, "run", basename)
            if command is not None:
                terminal.run_command(workingdir, command)

        compile_command = get_command(tab, "compile", basename)
        if compile_command is not None:
            no_terminal.run_command(workingdir, compile_command, run_after_compile)

    else:
        command = get_command(tab, something, basename)
        if command is not None:
            no_terminal.run_command(workingdir, command)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("commands", CommandsConfig())


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)

    # TODO: disable the menu items when they don't correspond to actual commands
    menubar.add_filetab_command("Run/Compile", partial(do_something, "compile"))
    menubar.add_filetab_command("Run/Run", partial(do_something, "run"))
    menubar.add_filetab_command("Run/Compile and Run", partial(do_something, "compilerun"))
    menubar.add_filetab_command("Run/Lint", partial(do_something, "lint"))
