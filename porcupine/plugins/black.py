import pathlib
import subprocess
import typing
from tkinter import messagebox

from porcupine import get_tab_manager, menubar, tabs


def run_black(code: str, path: typing.Optional[pathlib.Path]) -> typing.Optional[str]:
    # run black in subprocess just to make sure that it can't crash porcupine
    # set cwd so that black finds its config in pyproject.toml
    try:
        process = subprocess.Popen(
            ["black", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=(pathlib.Path.home() if path is None else path.parent),
        )
    except FileNotFoundError as e:
        messagebox.showerror(
            "Can't find black", str(e) + "\n\nMake sure that black is installed and try again."
        )
        return None

    (output, errors) = process.communicate(code.encode("utf-8"))
    if process.returncode != 0:
        messagebox.showerror(
            "Running black failed",
            (
                "Black exited with status code {process.returncode}.\n"
                + errors.decode("utf-8", errors="replace")
            ),
        )
        return None

    return output.decode("utf-8")


def callback() -> None:
    selected_tab = get_tab_manager().select()
    assert isinstance(selected_tab, tabs.FileTab)
    widget = selected_tab.textwidget
    before = widget.get("1.0", "end - 1 char")
    after = run_black(before, selected_tab.path)
    if after is None:
        # error
        return

    if before != after:
        widget["autoseparators"] = False
        widget.delete("1.0", "end - 1 char")
        widget.insert("1.0", after)
        widget.edit_separator()
        widget["autoseparators"] = True


def setup() -> None:
    menubar.get_menu("Tools/Python").add_command(label="black", command=callback)
    menubar.set_enabled_based_on_tab(
        "Tools/Python/black", (lambda tab: isinstance(tab, tabs.FileTab))
    )
