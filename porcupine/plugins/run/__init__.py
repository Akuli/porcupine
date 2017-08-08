"""Run files when pressing F5."""
# TODO: update this crap to not be limited to python

import functools
import logging
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import tkinter as tk

import porcupine
from porcupine import tabs, utils

log = logging.getLogger(__name__)


# __path__[0] is the directory where this __init__.py is
if platform.system() == 'Windows':
    run_script = 'windows_run.py'
else:
    run_script = 'sh_run.sh'
run_script = os.path.join(os.path.abspath(__path__[0]), run_script)


def _windows_run(path):
    if path is None:
        command = [utils.python_executable]
    else:
        command = [utils.python_executable, run_script, path]

    if not utils.running_pythonw:
        # windows wants to run python in the same terminal that
        # Porcupine was started from, this is the only way to open a
        # new command prompt i found and it works :) we need cmd
        # because start is built in to cmd (lol)
        command = ['cmd', '/c', 'start'] + command
    subprocess.Popen(command)


def _osx_terminal_app_run(path):
    if path is None:
        # this is easy because we don't need to pass arguments
        subprocess.Popen(['open', '-a', 'Terminal.app',
                          utils.python_executable])
        return

    # passing arguments is not easy, these things are wrong with this:
    #  - i needed to cheat and use stackoverflow because i don't
    #    have a mac :( http://stackoverflow.com/a/989357
    #  - new OSX versions keep the terminal open by
    #    default but older versions don't, so people using old
    #    OSX versions need to change their terminal settings
    # big thanks to go|dfish for testing this code!
    dirname, basename = os.path.split(path)
    command = [run_script, '--dont-wait', utils.python_executable,
               dirname, basename]

    quoted_command = ' '.join(map(shlex.quote, command))
    with tempfile.NamedTemporaryFile(
            'w', delete=False, prefix='porcupine-run-') as file:
        print('#!/bin/sh', file=file)
        print(quoted_command, file=file)
        print('rm', shlex.quote(file.name), file=file)  # see below

    os.chmod(file.name, 0o755)
    subprocess.Popen(['open', '-a', 'Terminal.app', file.name])
    # the terminal might be still opening when we get here,
    # that's why the file deletes itself


def _x11_like_run(path):
    terminal = os.environ.get('TERMINAL', 'x-terminal-emulator')
    if path is None:
        subprocess.Popen([terminal, '-e', utils.python_executable])
        return

    # sometimes x-terminal-emulator points to mate-terminal.wrapper,
    # it's a python script that changes some command line options and
    # runs mate-terminal but it breaks passing arguments with the -e
    # option for some reason
    if terminal == 'x-terminal-emulator':
        terminal = shutil.which(terminal)
        if terminal is None:
            raise FileNotFoundError(
                "x-terminal-emulator is not in $PATH")

        terminal = os.path.realpath(terminal)
        log.debug("x-terminal-emulator points to '%s'", terminal)
        if os.path.basename(terminal) == 'mate-terminal.wrapper':
            log.info("using mate-terminal instead of mate-terminal.wrapper")
            terminal = 'mate-terminal'

    dirname, basename = os.path.split(path)
    command = [run_script, utils.python_executable, dirname, basename]
    quoted_command = ' '.join(map(shlex.quote, command))
    subprocess.Popen([terminal, '-e', quoted_command])


# This figures out which terminal to use every time the user wants
# to run something, but it takes less than a millisecond so it
# doesn't really matter. This way the user can install a terminal
# while Porcupine is running without restarting it.
def run(path):
    if path is not None:
        path = os.path.abspath(path)

    widget = porcupine.get_main_window()    # any tk widget will do
    windowingsystem = widget.tk.call('tk', 'windowingsystem')
    if windowingsystem == 'win32':
        _windows_run(path)
    elif windowingsystem == 'aqua' and not os.environ.get('TERMINAL', ''):
        _osx_terminal_app_run(path)
    else:
        _x11_like_run(path)


def run_this_file():
    filetab = porcupine.get_tab_manager().current_tab
    if filetab.path is None or not filetab.is_saved():
        filetab.save()
    if filetab.path is None:
        # user cancelled a save as dialog
        return
    run(filetab.path)


def setup():
    open_prompt = functools.partial(run, None)
    porcupine.add_action(run_this_file, "Run/Run File", ("F5", "<F5>"),
                         [tabs.FileTab])
    porcupine.add_action(open_prompt, "Run/Interactive Prompt",
                         ("Ctrl+I", "<Control-i>"))


if __name__ == '__main__':
    # simple test
    with tempfile.TemporaryDirectory() as tempdir:
        script = os.path.join(tempdir, 'hello.py')
        with open(script, 'w') as f:
            print("print('hello world')", file=f)

        root = tk.Tk()
        button = tk.Button(root, text="run", command=lambda: run(script))
        button.pack()
        root.mainloop()
