"""Run files when pressing F5."""
# TODO: support compiling and linting somehow in the editor window
# TODO: display the status code when the program finishes?

import functools
import logging
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import tkinter as tk
from tkinter import messagebox

from porcupine import actions, filetypes, get_tab_manager, tabs, utils

log = logging.getLogger(__name__)


# __path__[0] is the directory where this __init__.py is
if platform.system() == 'Windows':
    run_script = 'windows_run.py'
else:
    run_script = 'bash_run.sh'
run_script = os.path.join(os.path.abspath(__path__[0]), run_script)


# getting this to work in powershell turned out to be hard :(
def _run_in_windows_cmd(blue_message, workingdir, command):
    # TODO: test this
    command = [utils.python_executable, run_script, blue_message,
               workingdir] + command
    if not utils.running_pythonw:
        # windows wants to run python in the same terminal that
        # Porcupine was started from, this is the only way to open a
        # new command prompt i found and it works :) we need cmd
        # because start is built in to cmd (lol)
        command = ['cmd', '/c', 'start'] + command
    subprocess.Popen(command)


def _run_in_osx_terminal_app(blue_message, workingdir, command):
    # passing arguments is not easy, these things are wrong with this:
    #  - i needed to cheat and use stackoverflow because i don't
    #    have a mac :( http://stackoverflow.com/a/989357
    #  - new OSX versions keep the terminal open by
    #    default but older versions don't, so people using old
    #    OSX versions need to change their terminal settings
    # big thanks to go|dfish for testing an older version of this code!
    # this exact code is NOT TESTED :/
    real_command = [run_script, '--dont-wait', blue_message,
                    workingdir] + command
    with tempfile.NamedTemporaryFile(
            'w', delete=False, prefix='porcupine-run-') as file:
        print('#!' + shutil.which('bash'), file=file)
        print('rm', shlex.quote(file.name), file=file)  # see below
        print(' '.join(map(shlex.quote, real_command)), file=file)

    os.chmod(file.name, 0o755)
    subprocess.Popen(['open', '-a', 'Terminal.app', file.name])
    # the terminal might be still opening when we get here, that's why
    # the file deletes itself
    # right now the file removes itself before it runs the actual command so
    # it's removed even if the command is interrupted


def _run_in_x11_like_terminal(blue_message, workingdir, command):
    terminal = os.environ.get('TERMINAL', 'x-terminal-emulator')

    # sometimes x-terminal-emulator points to mate-terminal.wrapper,
    # it's a python script that changes some command line options and
    # runs mate-terminal but it breaks passing arguments with the -e
    # option for some reason
    if terminal == 'x-terminal-emulator':
        terminal = shutil.which(terminal)
        if terminal is None:
            raise FileNotFoundError("x-terminal-emulator is not in $PATH")

        terminal = os.path.realpath(terminal)
        log.debug("x-terminal-emulator points to '%s'", terminal)
        if os.path.basename(terminal) == 'mate-terminal.wrapper':
            log.info("using mate-terminal instead of mate-terminal.wrapper")
            terminal = 'mate-terminal'

    real_command = [run_script, blue_message, workingdir] + command
    subprocess.Popen([terminal, '-e',
                      ' '.join(map(shlex.quote, real_command))])


# this figures out which terminal to use every time the user wants to run
# something but it doesn't really matter, this way the user can install a
# terminal while porcupine is running without restarting porcupine
def run(workingdir, command):
    blue_message = ' '.join(map(utils.quote, command))

    widget = get_tab_manager()    # any tkinter widget works
    windowingsystem = widget.tk.call('tk', 'windowingsystem')

    if windowingsystem == 'win32':
        _run_in_windows_cmd(blue_message, workingdir, command)
    elif windowingsystem == 'aqua' and not os.environ.get('TERMINAL', ''):
        _run_in_osx_terminal_app(blue_message, workingdir, command)
    else:
        _run_in_x11_like_terminal(blue_message, workingdir, command)


def run_this_file():
    filetab = get_tab_manager().current_tab
    assert isinstance(filetab, tabs.FileTab)
    if filetab.path is None or not filetab.is_saved():
        filetab.save()
        if filetab.path is None:
            # user cancelled a save as dialog
            return

    # FIXME: the run button should be grayed out instead of this
    if not filetab.filetype.has_command('run_command'):
        messagebox.showerror("Error", (
            "I don't know how to run %r files :(\n\n"
            "You can fix this by going to Edit \N{rightwards arrow} "
            "Porcupine Settings \N{rightwards arrow} File Types."
            % filetab.filetype.name))
        return

    workingdir, basename = os.path.split(filetab.path)
    command = filetab.filetype.get_command('run_command', basename)
    run(workingdir, command)


def setup():
    runnable = [filetype.name for filetype in filetypes.get_all_filetypes()
                if filetype.has_command('run_command')]
    actions.add_command("Run/Run File", run_this_file, '<F5>',
                        filetype_names=runnable)


if __name__ == '__main__':
    # simple test
    with tempfile.TemporaryDirectory() as tempdir:
        script = os.path.join(tempdir, 'hello.py')
        with open(script, 'w') as f:
            print("print('hello world')", file=f)

        root = tk.Tk()
        button = tk.Button(root, text="run",
                           command=lambda: run('.', [sys.executable, script]))
        button.pack()
        root.mainloop()
