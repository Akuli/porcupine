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

from porcupine import get_main_window, utils
from porcupine.plugins.run import common

log = logging.getLogger(__name__)

_this_dir = Path(__file__).absolute().parent
if sys.platform == "win32":
    run_script = _this_dir / "windows_run.py"
else:
    run_script = _this_dir / "bash_run.sh"


# getting this to work in powershell turned out to be hard :(
def _run_in_windows_cmd(command: str, cwd: Path, env: dict[str, str]) -> None:
    log.debug("using Windows command prompt")

    real_command = [str(utils.python_executable), str(run_script), str(cwd), command]
    if not utils.running_pythonw:
        # windows wants to run python in the same terminal that
        # Porcupine was started from, this is the only way to open a
        # new command prompt i found and it works :) we need cmd
        # because start is built in to cmd (lol)
        real_command = ["cmd", "/c", "start"] + real_command
    subprocess.Popen(real_command, env=env)


def _run_in_macos_terminal_app(command: str, cwd: Path, env: dict[str, str]) -> None:
    log.debug("using MacOS terminal.app")
    assert shutil.which("bash") is not None

    with tempfile.NamedTemporaryFile("w", delete=False, prefix="porcupine-run-") as file:
        print("#!/usr/bin/env bash", file=file)
        print("rm", shlex.quote(file.name), file=file)  # runs even if command is interrupted
        print(
            shlex.quote(str(run_script)),
            "--dont-wait",
            shlex.quote(str(cwd)),
            shlex.quote(command),
            file=file,
        )

    os.chmod(file.name, 0o755)
    subprocess.Popen(["open", "-a", "Terminal.app", file.name], env=env)
    # the terminal might be still opening when we get here, that's why
    # the file deletes itself
    # right now the file removes itself before it runs the actual command so
    # it's removed even if the command is interrupted


def _run_in_x11_like_terminal(command: str, cwd: Path, env: dict[str, str]) -> None:
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

    real_command = [str(run_script), str(cwd), command]
    real_command.extend(map(str, command))
    subprocess.Popen([terminal, "-e", " ".join(map(shlex.quote, real_command))], env=env)


# this figures out which terminal to use every time the user wants to run
# something but it doesn't really matter, this way the user can install a
# terminal while porcupine is running without restarting porcupine
def run_command(command: str, cwd: Path) -> None:
    log.info(f"Running {command} in {cwd}")

    env = common.prepare_env()
    widget = get_main_window()  # any tkinter widget works
    windowingsystem = widget.tk.call("tk", "windowingsystem")

    if windowingsystem == "win32":
        _run_in_windows_cmd(command, cwd, env)
    elif windowingsystem == "aqua" and not os.environ.get("TERMINAL", ""):
        _run_in_macos_terminal_app(command, cwd, env)
    else:
        _run_in_x11_like_terminal(command, cwd, env)
