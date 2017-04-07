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

from porcupine import dirs, utils

log = logging.getLogger(__name__)
_scriptdir = os.path.join(dirs.installdir, 'scripts')


if platform.system() == 'Windows':
    if utils.running_pythonw():
        # pythonw.exe is like python.exe but hides stdout and stderr
        _python = sys.executable[:-5] + sys.executable[-4:]  # get rid of 'w'
    else:
        # porcupine was started from command prompt or powershell
        _python = sys.executable

    def run(path):
        command = [_python, os.path.join(_scriptdir, 'windows_run.py'), path]
        if not utils.running_pythonw():
            # windows wants to run python in the same terminal that
            # Porcupine was started from, this is the only way to open a
            # new command prompt i found and it works :^) we need cmd
            # because start is built in to cmd (lol)
            command = ['cmd', '/c', 'start'] + command
        subprocess.Popen(command)

else:
    # We can't assume X11 or Aqua yet because someone might be running
    # X11 on OSX and we can't check that with tkinter yet.
    # This figures out which terminal to use every time the user wants
    # to run something, but it takes less than a millisecond so it
    # doesn't really matter. This way the user can install a terminal
    # while Porcupine is running without restarting it.

    def run(path):
        dirname, basename = os.path.split(os.path.abspath(path))
        command = [os.path.join(_scriptdir, 'sh_run.sh'),
                   sys.executable, dirname, basename]

        windowingsystem = utils.get_root().tk.call('tk', 'windowingsystem')
        if windowingsystem == 'aqua' and 'TERMINAL' not in os.environ:
            # use OSX's default Terminal.app
            # these things are wrong with this:
            #  - i needed to cheat and use stackoverflow because i don't
            #    have a mac :( http://stackoverflow.com/a/989357
            #  - new OSX versions seem to keep the terminal open by
            #    default but older versions don't, so people using a new
            #    OSX need to change their terminal settings
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

        else:
            env_terminal = os.environ.get('TERMINAL', 'x-terminal-emulator')
            terminal = shutil.which(env_terminal)
            if terminal is None:
                log.error("shutil.which(%r) returned None" % env_terminal)
                messagebox.showerror(
                    "Terminal not found",
                    ("Cannot find %s in $PATH. Make sure that you have " +
                     "a terminal installed and try again.") % env_terminal)
                return

            if env_terminal == 'x-terminal-emulator':
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
