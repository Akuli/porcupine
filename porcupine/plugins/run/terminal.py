"""Run commands in a new terminal window."""
from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import messagebox
from typing import Union

from porcupine import get_main_window, utils

log = logging.getLogger(__name__)

_this_dir = Path(__file__).absolute().parent
if sys.platform == "win32":
    run_script = _this_dir / "windows_run.py"
else:
    run_script = _this_dir / "bash_run.sh"


# getting this to work in powershell turned out to be hard :(
def _run_in_windows_cmd(blue_message: str, workingdir: Path, command: list[str]) -> None:
    log.debug("using Windows command prompt")

    command = [
        str(utils.python_executable),
        str(run_script),
        blue_message,
        str(workingdir),
    ] + command

    if not utils.running_pythonw:
        # windows wants to run python in the same terminal that
        # Porcupine was started from, this is the only way to open a
        # new command prompt i found and it works :) we need cmd
        # because start is built in to cmd (lol)
        command = ["cmd", "/c", "start"] + command
    subprocess.Popen(command)


def _run_in_osx_terminal_app(blue_message: str, workingdir: Path, command: list[str]) -> None:
    log.debug("using OSX terminal.app")

    bash = shutil.which("bash")
    assert bash is not None

    # passing arguments is not easy, these things are wrong with this:
    #  - i needed to cheat and use stackoverflow because i don't
    #    have a mac :( http://stackoverflow.com/a/989357
    #  - new OSX versions keep the terminal open by
    #    default but older versions don't, so people using old
    #    OSX versions need to change their terminal settings
    # big thanks to go|dfish for testing an older version of this code!
    # this exact code is NOT TESTED :/
    real_command = [str(run_script), "--dont-wait", blue_message, str(workingdir)] + list(
        map(str, command)
    )
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="porcupine-run-") as file:
        print("#!/usr/bin/env bash", file=file)
        print("rm", shlex.quote(file.name), file=file)  # see below
        print(" ".join(map(shlex.quote, real_command)), file=file)

    os.chmod(file.name, 0o755)
    subprocess.Popen(["open", "-a", "Terminal.app", file.name])
    # the terminal might be still opening when we get here, that's why
    # the file deletes itself
    # right now the file removes itself before it runs the actual command so
    # it's removed even if the command is interrupted


def _run_in_x11_like_terminal(blue_message: str, workingdir: Path, command: list[str]) -> None:
    terminal: str = os.environ.get("TERMINAL", "x-terminal-emulator")

    # to config what x-terminal-emulator is:
    #
    #   $ sudo update-alternatives --config x-terminal-emulator
    #
    # TODO: document this
    if terminal == "x-terminal-emulator":
        log.debug("using x-terminal-emulator")

        terminal_or_none = shutil.which(terminal)
        if terminal_or_none is None:
            log.warning("x-terminal-emulator not found")

            # Ellusion told me on irc that porcupine didn't find his
            # xfce4-terminal, and turned out he had no x-terminal-emulator...
            # i'm not sure why, but this should work
            #
            # well, turns out he's using arch, so... anything could be wrong
            terminal_or_none = shutil.which("xfce4-terminal")
            if terminal_or_none is None:
                # not much more can be done
                messagebox.showerror(
                    "x-terminal-emulator not found",
                    "Cannot find x-terminal-emulator in $PATH. "
                    "Are you sure that you have a terminal installed?",
                )
                return

        terminal_path = Path(terminal_or_none)
        log.info(f"found a terminal: {terminal_path}")

        terminal_path = terminal_path.resolve()
        log.debug(f"absolute path to terminal: {terminal_path}")

        # sometimes x-terminal-emulator points to mate-terminal.wrapper,
        # it's a python script that changes some command line options
        # and runs mate-terminal but it breaks passing arguments with
        # the -e option for some reason
        if terminal_path.name == "mate-terminal.wrapper":
            log.info("using mate-terminal instead of mate-terminal.wrapper")
            terminal = "mate-terminal"
        else:
            terminal = str(terminal_path)
    else:
        log.debug(f"using $TERMINAL or fallback 'x-terminal-emulator', got {terminal!r}")

    if shutil.which(terminal) is None:
        messagebox.showerror(
            f"{terminal!r} not found",
            f"Cannot find {terminal!r} in $PATH. Try setting $TERMINAL to a path to a working"
            " terminal program.",
        )
        return

    real_command = [str(run_script), blue_message, str(workingdir)]
    real_command.extend(map(str, command))
    subprocess.Popen([terminal, "-e", " ".join(map(shlex.quote, real_command))])


# this figures out which terminal to use every time the user wants to run
# something but it doesn't really matter, this way the user can install a
# terminal while porcupine is running without restarting porcupine
def run_command(workingdir: Path, command: list[str]) -> None:
    blue_message = " ".join(map(utils.quote, command))

    widget = get_main_window()  # any tkinter widget works
    windowingsystem = widget.tk.call("tk", "windowingsystem")

    if windowingsystem == "win32":
        _run_in_windows_cmd(blue_message, workingdir, command)
    elif windowingsystem == "aqua" and not os.environ.get("TERMINAL", ""):
        _run_in_osx_terminal_app(blue_message, workingdir, command)
    else:
        _run_in_x11_like_terminal(blue_message, workingdir, command)
