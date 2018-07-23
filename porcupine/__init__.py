# flake8: noqa
"""Porcupine is a simple editor.

You are probably reading this because you want to learn how Porcupine
works or write fun plugins for it. I recommend getting started with the
plugin API documentation:

    https://akuli.github.io/porcupine/
"""

import os
import shutil
import subprocess

version_info = (0, 68, 0)        # this is updated with bump.py
__version__ = '%d.%d.%d' % version_info
__author__ = 'Akuli'
__copyright__ = 'Copyright (c) 2017 Akuli'
__license__ = 'MIT'

# attach git stuff to the version if this isn't installed
here = os.path.dirname(os.path.abspath(__file__))
if (os.path.isdir(os.path.join(here, '..', '.git')) and
    shutil.which('git') is not None):
    # probably a git repo, not installed
    try:
        __version__ += '-git-' + subprocess.check_output(
            ['git', 'log', '--pretty=format:%h', '-n', '1']).decode('ascii')
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        pass

from porcupine._run import (init, get_init_kwargs, run, quit, get_main_window,
                            get_tab_manager)   # noqa
