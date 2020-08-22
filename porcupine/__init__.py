"""Porcupine is a simple editor.

You are probably reading this because you want to learn how Porcupine
works or write fun plugins for it. I recommend getting started with the
plugin API documentation:

    https://akuli.github.io/porcupine/
"""

import pathlib
import shutil
import subprocess

from porcupine import _state

version_info = (0, 78, 0)        # this is updated with bump.py
__version__ = '%d.%d.%d' % version_info
__author__ = 'Akuli'
__copyright__ = 'Copyright (c) 2017-2020 Akuli'
__license__ = 'MIT'

# attach git stuff to the version if this isn't installed
_here = pathlib.Path(__file__).absolute().parent
if (_here.parent / '.git').is_dir() and shutil.which('git') is not None:
    # running porcupine from git repo
    try:
        __version__ += '+git.' + subprocess.check_output(
            ['git', 'log', '--pretty=format:%h', '-n', '1']).decode('ascii')
    except (OSError, subprocess.CalledProcessError, UnicodeError):   # pragma: no cover
        pass

quit = _state.quit
get_main_window = _state.get_main_window
get_parsed_args = _state.get_parsed_args
get_tab_manager = _state.get_tab_manager
