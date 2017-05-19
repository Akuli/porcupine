"""Run files when pressing F5."""

import logging
import os
import platform
import shlex
import shutil
import subprocess
import tempfile
import tkinter as tk
from tkinter import messagebox

from porcupine import tabs, utils

log = logging.getLogger(__name__)

# __path__[0] is the directory where this __init__.py is
_scriptdir = os.path.abspath(__path__[0])


def _windows_run(path):
    command = [utils.python_executable,
               os.path.join(_scriptdir, 'windows_run.py'), path]
    if not utils.running_pythonw:
        # windows wants to run python in the same terminal that
        # Porcupine was started from, this is the only way to open a
        # new command prompt i found and it works :) we need cmd
        # because start is built in to cmd (lol)
        command = ['cmd', '/c', 'start'] + command
    subprocess.Popen(command)


def _osx_terminal_app_run(path):
    dirname, basename = os.path.split(path)
    command = [os.path.join(_scriptdir, 'sh_run.sh'), '--dont-wait',
               utils.python_executable, dirname, basename]

    # these things are wrong with this:
    #  - i needed to cheat and use stackoverflow because i don't
    #    have a mac :( http://stackoverflow.com/a/989357
    #  - new OSX versions keep the terminal open by
    #    default but older versions don't, so people using old
    #    OSX versions need to change their terminal settings
    # big thanks to go|dfish for testing this code!
    quoted_command = ' '.join(map(shlex.quote, command))
    with tempfile.NamedTemporaryFile('w', delete=False,
                                     prefix='porcupine-') as file:
        print('#!/bin/sh', file=file)
        print(quoted_command, file=file)
        print('rm', shlex.quote(file.name), file=file)  # see below

    os.chmod(file.name, 0o755)
    subprocess.Popen(['open', '-a', 'Terminal.app', file.name])
    # the terminal might be still opening when we get here,
    # that's why the file deletes itself


def _x11_like_run(path):
    dirname, basename = os.path.split(path)
    command = [os.path.join(_scriptdir, 'sh_run.sh'),
               utils.python_executable, dirname, basename]

    env_terminal = os.environ.get('TERMINAL', 'x-terminal-emulator')
    terminal = shutil.which(env_terminal)
    if terminal is None:
        log.error("shutil.which(%r) returned None" % env_terminal)
        messagebox.showerror(
            "Terminal not found",
            ("Cannot find %s in $PATH. Make sure that you have " +
             "a terminal program installed and try again.") % env_terminal)
        return

    if env_terminal == 'x-terminal-emulator':
        terminal = os.path.realpath(terminal)
        log.debug("x-terminal-emulator points to '%s'", terminal)

        if os.path.basename(terminal) == 'mate-terminal.wrapper':
            # it's a python script that changes some command line
            # options and runs mate-terminal, but it breaks the -e
            # option for some reason
            log.info("using mate-terminal instead of mate-terminal.wrapper")
            terminal = 'mate-terminal'

    quoted_command = ' '.join(map(shlex.quote, command))
    subprocess.Popen([terminal, '-e', quoted_command])


# This figures out which terminal to use every time the user wants
# to run something, but it takes less than a millisecond so it
# doesn't really matter. This way the user can install a terminal
# while Porcupine is running without restarting it.
def run(path):
    path = os.path.abspath(path)

    windowingsystem = utils.get_root().tk.call('tk', 'windowingsystem')
    if windowingsystem == 'win32':
        _windows_run(path)
    elif windowingsystem == 'aqua' and 'TERMINAL' not in os.environ:
        _osx_terminal_app_run(path)
    else:
        _x11_like_run(path)


def setup(editor):
    def run_current_file():
        filetab = editor.tabmanager.current_tab
        if filetab.path is None or not filetab.is_saved():
            filetab.save()
        if filetab.path is None:
            # user cancelled a save as dialog
            return
        run(filetab.path)

    if platform.system() == 'Windows':
        menupath = "Run/Run in Command Prompt"
    else:
        menupath = "Run/Run in Terminal"
    editor.add_action(run_current_file, menupath, "F5", "<F5>",
                      [tabs.FileTab])


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
