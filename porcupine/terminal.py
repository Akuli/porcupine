import io
import logging
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

import tkinter as tk
from tkinter import messagebox


log = logging.getLogger(__name__)
_scriptdir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'scripts')


if platform.system() == 'Windows':
    if os.path.basename(sys.executable).lower() == 'pythonw.exe':
        # pythonw.exe is like python.exe but hides stdout and stderr
        _running_pythonw = True
        _python = sys.executable[:-5] + sys.executable[-4:]  # get rid of 'w'
    else:
        # porcupine was started from command prompt or powershell
        _running_pythonw = False
        _python = sys.executable

    def run(path):
        dirname, basename = os.path.split(os.path.abspath(path))
        command = [os.path.join(_scriptdir, 'windows_run.bat'),
                   _python, dirname, basename]
        if not _running_pythonw:
            # windows wants to run python in the same terminal that
            # Porcupine was started from, this is the only way to open a
            # new command prompt i found and it works :^) we need cmd
            # because start is built in to cmd (lol)
            command = ['cmd', '/c', 'start'] + command
        subprocess.Popen(command)

else:
    # we can't assume X11 or Aqua yet because someone might be running
    # X11 on OSX and we can't check that with tkinter yet
    _windowingsystem = None

    def run(path):
        global _windowingsystem

        if _windowingsystem is None:
            # tkinter doesn't expose the default root window anywhere so
            # this is kind of weird
            dummy = tk.Label()
            _windowingsystem = dummy.tk.call('tk', 'windowingsystem')
            dummy.destroy()

        dirname, basename = os.path.split(os.path.abspath(path))
        command = [os.path.join(_scriptdir, 'sh_run.sh'),
                   sys.executable, dirname, basename]

        if _windowingsystem == 'aqua':
            # these things are wrong with this:
            #  - i needed to cheat and use stackoverflow because i don't
            #    have a mac :( http://stackoverflow.com/a/989357
            #  - new OSX versions seem to keep the terminal open by
            #    default but older versions don't, so people using a new
            #    OSX need to change their terminal settings
            # big thanks to go|dfish for testing this code!
            quoted_command = ' '.join(map(shlex.quote, command))
            file = tempfile.NamedTemporaryFile(
                prefix='porcupine-', suffix='.command', delete=False)

            with io.TextIOWrapper(file.file) as textfile:
                print('#!/bin/sh', file=textfile)
                print(quoted_command, file=textfile)
                print('rm', shlex.quote(file.name), file=textfile)  # see below

            os.chmod(file.name, 0o755)
            subprocess.Popen(['open', file.name])
            # the terminal might be still opening when we get here,
            # that's why the file deletes itself

        else:
            terminal = shutil.which('x-terminal-emulator')
            if terminal is None:
                log.error("shutil.which('x-terminal-emulator') returned None")
                messagebox.showerror(
                    "Terminal not found",
                    "Cannot find x-terminal-emulator in $PATH. Make sure " +
                    "that you have a terminal installed and try again.")
                return

            while os.path.islink(terminal):
                terminal = os.readlink(terminal)
            log.debug("x-terminal-emulator points to '%s'", terminal)

            if os.path.basename(terminal) == 'mate-terminal.wrapper':
                # it's a python script that changes some command line
                # options and runs mate-terminal, but it breaks the -e
                # option for some reason
                log.info("using mate-terminal instead of "
                         "mate-terminal.wrapper")
                terminal = 'mate-terminal'

            quoted_command = ' '.join(map(shlex.quote, command))
            subprocess.Popen([terminal, '-e', quoted_command])


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
