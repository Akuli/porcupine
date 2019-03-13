"""Run commands in a new terminal window."""
import logging
import os
import platform
import shlex
import shutil
import subprocess
import tempfile

import teek as tk

from porcupine import get_main_window, utils


log = logging.getLogger(__name__)

_this_dir = os.path.dirname(os.path.abspath(__file__))
if platform.system() == 'Windows':
    run_script = os.path.join(_this_dir, 'windows_run.py')
else:
    run_script = os.path.join(_this_dir, 'bash_run.sh')


# getting this to work in powershell turned out to be hard :(
# TODO: tests
def _run_in_windows_cmd(blue_message, workingdir, command):
    log.debug("using Windows command prompt")

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
    log.debug("using OSX terminal.app")

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

    if terminal == 'x-terminal-emulator':
        log.debug("using x-terminal-emulator")

        terminal = shutil.which(terminal)
        if terminal is None:
            log.warning("x-terminal-emulator not found")

            # Ellusion told me on irc that porcupine didn't find his
            # xfce4-terminal, and turned out he had no x-terminal-emulator...
            # i'm not sure why, but this should work
            #
            # well, turns out he's using arch, so... anything could be wrong
            terminal = shutil.which('xfce4-terminal')
            if terminal is None:
                # not much more can be done
                tk.dialog.error(
                    "x-terminal-emulator not found",
                    "Cannot find x-terminal-emulator in $PATH. "
                    "Are you sure that you have a terminal installed?")
                return

        log.info("found a terminal: %s", terminal)

        terminal = os.path.realpath(terminal)
        log.debug("x-terminal-emulator points to '%s'", terminal)

        # sometimes x-terminal-emulator points to mate-terminal.wrapper,
        # it's a python script that changes some command line options
        # and runs mate-terminal but it breaks passing arguments with
        # the -e option for some reason
        if os.path.basename(terminal) == 'mate-terminal.wrapper':
            log.info("using mate-terminal instead of mate-terminal.wrapper")
            terminal = 'mate-terminal'
    else:
        log.debug("using $TERMINAL, it's set to %r" % terminal)

    if shutil.which(terminal) is None:
        tk.dialog.error(
            "%r not found" % terminal,
            "Cannot find %r in $PATH. "
            "Try setting $TERMINAL to a path to a working terminal program."
            % terminal)
        return

    real_command = [run_script, blue_message, workingdir] + command
    subprocess.Popen([terminal, '-e',
                      ' '.join(map(shlex.quote, real_command))])


# this figures out which terminal to use every time the user wants to run
# something but it doesn't really matter, this way the user can install a
# terminal while porcupine is running without restarting porcupine
def run_command(workingdir, command):
    blue_message = ' '.join(map(utils.quote, command))

    if tk.windowingsystem() == 'win32':
        _run_in_windows_cmd(blue_message, workingdir, command)
    elif tk.windowingsystem() == 'aqua' and not os.environ.get('TERMINAL', ''):
        _run_in_osx_terminal_app(blue_message, workingdir, command)
    else:
        _run_in_x11_like_terminal(blue_message, workingdir, command)
