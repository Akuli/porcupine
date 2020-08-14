"""Run keybindings.tcl and default_keybindings.tcl when Porcupine starts."""

import pathlib
import tkinter

from porcupine import dirs, get_main_window, settings


def setup() -> None:
    porcupine_dir = pathlib.Path(__file__).absolute().parent.parent
    default_path = porcupine_dir / 'default_keybindings.tcl'
    user_path = dirs.configdir / 'keybindings.tcl'

    notebook = settings.get_notebook()
    [config_file_section] = [
        notebook.nametowidget(tab) for tab in notebook.tabs()
        if notebook.tab(tab, 'text') == 'Config Files'
    ]
    assert isinstance(config_file_section, tkinter.ttk.Frame)
    settings.add_config_file_button(config_file_section, user_path)

    try:
        with user_path.open('x') as file:
            file.write('''\
# This Tcl file is executed when Porcupine starts. It's meant to be used for
# custom key bindings. See Porcupine's default key binding file for examples:
#
#    https://github.com/Akuli/porcupine/blob/master/porcupine/default_keybindings.tcl
''')
    except FileExistsError:
        pass

    try:
        get_main_window().tk.call('source', default_path)
        get_main_window().tk.call('source', user_path)
    except tkinter.TclError:
        # more verbose error message than default, including file names and line numbers
        raise tkinter.TclError(get_main_window().getvar('errorInfo')) from None
