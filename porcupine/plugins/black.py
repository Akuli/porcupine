import logging
import pathlib
import shutil
import subprocess
import traceback
import typing
from tkinter import messagebox

from porcupine import get_tab_manager, menubar, tabs, textwidget, utils
from porcupine.plugins import python_venv

log = logging.getLogger(__name__)


def run_black(code: str, path: typing.Optional[pathlib.Path]) -> typing.Optional[str]:
    black = shutil.which("black")
    log.debug(f"black from PATH: {black}")
    if path is None:
        log.debug("No file path available, using black from PATH")
    else:
        project_root = utils.find_project_root(path)
        venv = python_venv.get_venv(project_root)
        if venv is None:
            log.debug(f"No venv found from {project_root}")
        else:
            black_path = python_venv.get_exe(venv, "black")
            if black_path is not None:
                black = str(black_path)
                log.info(f"Found black from venv: {black}")
            else:
                log.debug(f"No black in venv: {venv}")

    log.info(f"Using black: {black}")
    if black is None:
        log.exception("can't find black")
        messagebox.showerror("Can't find black", "Make sure that black is installed and try again.")
        return None

    try:
        # run black in subprocess just to make sure that it can't crash porcupine
        # set cwd so that black finds its config in pyproject.toml
        result = subprocess.run(
            [black, "-"],
            check=True,
            stdout=subprocess.PIPE,
            cwd=(pathlib.Path.home() if path is None else path.parent),
            input=code.encode("utf-8"),
        )
        return result.stdout.decode("utf-8")
    except Exception as e:
        log.exception(e)
        messagebox.showerror("Running black failed", traceback.format_exc())
        return None


def callback() -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    before = tab.textwidget.get("1.0", "end - 1 char")
    after = run_black(before, tab.path)

    if after is not None and before != after:
        with textwidget.change_batch(tab.textwidget):
            tab.textwidget.replace("1.0", "end - 1 char", after)


def setup() -> None:
    menubar.get_menu("Tools/Python").add_command(label="black", command=callback)
    menubar.set_enabled_based_on_tab(
        "Tools/Python/black", (lambda tab: isinstance(tab, tabs.FileTab))
    )
