"""Run autopep8 on the file being edited. This is in the Python submenu of the Tools menu."""
import platform
import subprocess
from typing import Optional

from porcupine import get_tab_manager, menubar, tabs, utils


def run_autopep8(code: str) -> Optional[str]:
    try:
        import autopep8  # type: ignore[import]
        autopep8 = autopep8     # silence pyflakes warning
    except ImportError:
        # this command is wrong in some cases, but most of the time
        # it's ok
        if platform.system() == 'Windows':
            pip_command = "py -m pip install autopep8"
            terminal = 'command prompt or PowerShell'
        else:
            pip_command = "python3 -m pip install --user autopep8"
            terminal = 'a terminal'

        utils.errordialog(
            "Cannot find autopep8",
            "Looks like autopep8 is not installed.\n" +
            f"You can install it by running this command on {terminal}:",
            pip_command)
        return None

    # autopep8's main() does some weird signal stuff, so we'll run it in
    # a subprocess just to make sure that the porcupine process is ok
    command = [str(utils.python_executable), '-m', 'autopep8', '-']
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (output, errors) = process.communicate(code.encode('utf-8'))

    if process.returncode != 0:
        utils.errordialog(
            "Running autopep8 failed",
            "autopep8 exited with status code %r." % process.returncode,
            errors.decode('utf-8', errors='replace'))
        return None

    return output.decode('utf-8')


def callback() -> None:
    selected_tab = get_tab_manager().select()
    assert isinstance(selected_tab, tabs.FileTab)
    widget = selected_tab.textwidget
    before = widget.get('1.0', 'end - 1 char')
    after = run_autopep8(before)
    if after is None:
        # error
        return

    if before != after:
        widget.config(autoseparators=False)
        widget.delete('1.0', 'end - 1 char')
        widget.insert('1.0', after)
        widget.edit_separator()
        widget.config(autoseparators=True)


def setup() -> None:
    # TODO: Python tabs only?
    menubar.get_menu("Tools/Python").add_command(label="autopep8", command=callback)
    menubar.set_enabled_based_on_tab("Tools/Python/autopep8", (lambda tab: isinstance(tab, tabs.FileTab)))
