"""Porcupine is a simple editor.

You are probably reading this because you want to learn how Porcupine
works or write fun plugins for it. I recommend getting started with the
plugin API documentation:

    https://akuli.github.io/porcupine/
"""

import sys

import appdirs

version_info = (0, 97, 0)  # this is updated with scripts/release.py
__version__ = "%d.%d.%d" % version_info
__author__ = "Akuli"
__copyright__ = "Copyright (c) 2017-2021 Akuli"
__license__ = "MIT"

if sys.platform in {"win32", "darwin"}:
    # these platforms like path names like "Program Files" or "Application Support"
    dirs = appdirs.AppDirs("Porcupine", "Akuli")
else:
    dirs = appdirs.AppDirs("porcupine", "akuli")

# Must be after creating dirs
from porcupine import _state

get_main_window = _state.get_main_window
get_parsed_args = _state.get_parsed_args
get_paned_window = _state.get_paned_window  # TODO: document this
get_tab_manager = _state.get_tab_manager
filedialog_kwargs = _state.filedialog_kwargs
quit = _state.quit
