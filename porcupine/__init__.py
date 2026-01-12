from porcupine import _state

version_info = (2024, 3, 31)  # this is updated with scripts/release.py
__version__ = "%d.%02d.%02d" % version_info
__author__ = "Akuli"
__copyright__ = "Copyright (c) 2017-2024, 2026 Akuli"
__license__ = "MIT"

get_main_window = _state.get_main_window
get_parsed_args = _state.get_parsed_args
get_horizontal_panedwindow = _state.get_horizontal_panedwindow  # TODO: document this
get_vertical_panedwindow = _state.get_vertical_panedwindow  # TODO: document this
get_tab_manager = _state.get_tab_manager
add_quit_callback = _state.add_quit_callback
quit = _state.quit
