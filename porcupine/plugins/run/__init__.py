"""Compile, run and lint files."""

import functools
import logging
import os

from porcupine import actions, filetypes, get_tab_manager, tabs

from . import terminal, no_terminal

log = logging.getLogger(__name__)


def do_something_to_this_file(something):
    tab = get_tab_manager().selected_tab
    assert isinstance(tab, tabs.FileTab)
    if tab.path is None or not tab.is_saved():
        tab.save()
        if tab.path is None:
            # user cancelled a save as dialog
            return

    workingdir, basename = os.path.split(tab.path)

    if something == 'run':
        command = tab.filetype.get_command('run_command', basename)
        terminal.run_command(workingdir, command)

    elif something == 'compilerun':
        def run_after_compile():
            command = tab.filetype.get_command('run_command', basename)
            terminal.run_command(workingdir, command)

        compile_command = tab.filetype.get_command('compile_command', basename)
        no_terminal.run_command(workingdir, compile_command, run_after_compile)

    else:
        assert something in {'compile', 'lint'}
        command = tab.filetype.get_command(something + '_command', basename)
        no_terminal.run_command(workingdir, command)


def get_filetype_names(has_what):
    return {filetype.name for filetype in filetypes.get_all_filetypes()
            if filetype.has_command(has_what)}


def setup():
    compilable = get_filetype_names('compile_command')
    runnable = get_filetype_names('run_command')
    lintable = get_filetype_names('lint_command')

    def create_callback(something):
        return functools.partial(do_something_to_this_file, something)

    actions.add_command("Run/Compile", create_callback('compile'),
                        '<F4>', filetype_names=compilable)
    actions.add_command("Run/Run", create_callback('run'),
                        '<F5>', filetype_names=runnable)
    actions.add_command("Run/Compile and Run", create_callback('compilerun'),
                        '<F6>', filetype_names=(compilable & runnable))
    actions.add_command("Run/Lint", create_callback('lint'),
                        '<F7>', filetype_names=lintable)
