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
def _run_in_windows_cmd(command: str | None, cwd: Path, env: dict[str, str]) -> None:
    log.debug("using Windows command prompt")

    if not command:
        cd_command = subprocess.list2cmdline(["cd", "/d", str(cwd)])
        subprocess.Popen(["cmd", "/K", cd_command], env=env)
        return

    real_command = [str(utils.python_executable), str(run_script), str(cwd), command]
    if not sys.executable.endswith((r"\Porcupine.exe", r"\pythonw.exe")):
        # Porcupine was started from a command prompt window.
        #
        # For some reason, windows wants to run the user's Python program in the
        # same command prompt window, so we tell it to open a new command prompt.
        real_command = ["cmd", "/c", "start"] + real_command

    subprocess.Popen(real_command, env=env)


def _run_in_macos_terminal_app(command: str | None, cwd: Path, env: dict[str, str]) -> None:
    log.debug("using MacOS terminal.app")

    if not command:
        subprocess.Popen(["open", "-a", "Terminal", str(cwd)], env=env)
        return

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


# TODO: Clean up this function, it works but could be more tidy
def _run_in_x11_like_terminal(command: str | None, cwd: Path, env: dict[str, str]) -> None:
    terminal: str | None = next(
        filter(
            lambda t: t is not None,
            (
                shutil.which(term)
                for term in (
                    os.environ.get("TERMINAL", "x-terminal-emulator"),
                    "mate-terminal",
                    "xfce4-terminal",
                    "st",
                    "lxterm",
                    "uxterm",
                    "xterm",
                )
            ),
        ),
        None,
    )

    # to config what x-terminal-emulator is:
    #
    #   $ sudo update-alternatives --config x-terminal-emulator
    #
    # TODO: document this

    if terminal is None:
        log.warning("terminal emulator not found")
        messagebox.showerror(
            "Terminal emulator not found",
            "Cannot find a terminal emulator in $PATH. "
            "Try setting $TERMINAL to a path to a working terminal program.",
        )
        return

    terminal_path = Path(terminal)
    log.info(f"found a terminal: {terminal_path}")

    terminal_path = terminal_path.resolve()
    log.debug(f"absolute path to terminal: {terminal_path}")

    terminal = str(terminal_path)

    if not terminal_path.exists():  # paranoid test case against broken symlinks
        messagebox.showerror(
            f"{terminal!r} not found",
            f"Cannot find {terminal!r} in $PATH. Try setting $TERMINAL to a path to a working"
            " terminal program.",
        )
        return

    if command:
        real_command = [str(run_script), str(cwd), command]
        if terminal_path.name in ("gnome-terminal", "mate-terminal", "terminology"):
            subprocess.Popen([terminal, "-e", " ".join(map(shlex.quote, real_command))], env=env)
        else:
            subprocess.Popen([terminal, "-e", *real_command], env=env)
    else:
        subprocess.Popen(terminal, cwd=cwd, env=env)


# this figures out which terminal to use every time the user wants to run
# something but it doesn't really matter, this way the user can install a
# terminal while porcupine is running without restarting porcupine
def run_command(command: str | None, cwd: Path) -> None:
    if command:
        log.info(f"Running {command} in {cwd}")
    else:
        log.info(f"Opening terminal in {cwd}")

    env = common.prepare_env()
    widget = get_main_window()  # any tkinter widget works
    windowingsystem = widget.tk.call("tk", "windowingsystem")

    if windowingsystem == "win32":
        _run_in_windows_cmd(command, cwd, env)
    elif windowingsystem == "aqua" and not os.environ.get("TERMINAL", ""):
        _run_in_macos_terminal_app(command, cwd, env)
    else:
        _run_in_x11_like_terminal(command, cwd, env)
