"""Porcupine is a simple editor.

You are probably reading this because you want to learn how Porcupine
works or write fun plugins for it. I recommend getting started with the
plugin API documentation:

    https://akuli.github.io/porcupine/
"""

import sys

import appdirs

version_info = (2022, 7, 29)  # this is updated with scripts/release.py
__version__ = "%d.%02d.%02d" % version_info
__author__ = "Akuli"
__copyright__ = "Copyright (c) 2017-2022 Akuli"
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
get_horizontal_panedwindow = _state.get_horizontal_panedwindow  # TODO: document this
get_vertical_panedwindow = _state.get_vertical_panedwindow  # TODO: document this
get_tab_manager = _state.get_tab_manager
filedialog_kwargs = _state.filedialog_kwargs
add_quit_callback = _state.add_quit_callback
quit = _state.quit
