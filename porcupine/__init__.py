"""Porcupine is a simple editor.

You are probably reading this because you want to learn how Porcupine
works or write fun plugins for it. I recommend getting started with the
plugin API documentation:

    https://akuli.github.io/porcupine/
"""

version_info = (0, 48, 1)        # this is updated with bump.py
__version__ = '%d.%d.%d' % version_info
__author__ = 'Akuli'
__copyright__ = 'Copyright (c) 2017 Akuli'
__license__ = 'MIT'

from porcupine._session import (    # noqa
    init, quit, get_main_window, get_tab_manager,
    new_file, open_file, add_action)
