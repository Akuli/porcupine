"""Compile, run and lint files."""

import functools
import logging
import os
import pathlib
import platform
import shlex
from typing import Callable, List, Optional

from porcupine import actions, get_tab_manager, tabs, utils

from . import terminal, no_terminal

log = logging.getLogger(__name__)


def get_command(tab: tabs.FileTab, something_command: str, basename: str) -> Optional[List[str]]:
    assert os.sep not in basename, "%r is not a basename" % basename
    template = tab.settings.get(something_command, str)
    if not template.strip():
        return None

    exts = ''.join(pathlib.Path(basename).suffixes)
    no_ext = pathlib.Path(basename).stem
    format_args = {
        'file': basename,
        'no_ext': pathlib.Path(basename).stem,
        'no_exts': basename[:-len(exts)] if exts else basename,
        'python': 'py' if platform.system() == 'Windows' else 'python3',
        'exe': f'{no_ext}.exe' if platform.system() == 'Windows' else f'./{no_ext}',
    }
    # TODO: is this really supposed to be shlex.split even on windows?
    result = [part.format(**format_args) for part in shlex.split(template)]
    assert result
    return result


def do_something_to_this_file(something: str) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    if tab.path is None or not tab.is_saved():
        tab.save()
        if tab.path is None:
            # user cancelled a save as dialog
            return

    workingdir = tab.path.parent
    basename = tab.path.name

    if something == 'run':
        command = get_command(tab, 'run_command', basename)
        if command is not None:
            terminal.run_command(workingdir, command)

    elif something == 'compilerun':
        def run_after_compile() -> None:
            assert isinstance(tab, tabs.FileTab)
            command = get_command(tab, 'run_command', basename)
            if command is not None:
                terminal.run_command(workingdir, command)

        compile_command = get_command(tab, 'compile_command', basename)
        if compile_command is not None:
            no_terminal.run_command(workingdir, compile_command, run_after_compile)

    else:
        assert something in {'compile', 'lint'}
        command = get_command(tab, something + '_command', basename)
        if command is not None:
            no_terminal.run_command(workingdir, command)


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        tab.settings.add_option('compile_command', '')
        tab.settings.add_option('run_command', '')
        tab.settings.add_option('lint_command', '')


def setup() -> None:
    def create_callback(something: str) -> Callable[[], None]:
        return functools.partial(do_something_to_this_file, something)

    # TODO: disable the menu items when they don't correspond to actual commands
    actions.add_command("Run/Compile", create_callback('compile'),
                        '<F4>', tabtypes=[tabs.FileTab])
    actions.add_command("Run/Run", create_callback('run'),
                        '<F5>', tabtypes=[tabs.FileTab])
    actions.add_command("Run/Compile and Run", create_callback('compilerun'),
                        '<F6>', tabtypes=[tabs.FileTab])
    actions.add_command("Run/Lint", create_callback('lint'),
                        '<F7>', tabtypes=[tabs.FileTab])

    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
