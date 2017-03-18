import configparser
import glob
import os
import sys
import tkinter as tk


# config can't just be a ConfigParser object because i want the changes
# to be applied immediately when something is selected in the setting
# dialog, but color_themes can be because themes cannot be edited or
# created on-the-fly (yet)
config = {}  # {'section:key': tkintervar}
color_themes = configparser.ConfigParser(default_section='Default')

_here = os.path.dirname(os.path.abspath(__file__))
_user_config_dir = os.path.join(os.path.expanduser('~'), '.porcupine')

# We can't create StringVar etc. here because they need a root window.
# This : syntax might seem a bit odd at first, but I think it's a nice
# and simple way to do this. Flat is better than nested :)
_config_info = {
    'files:encoding': tk.StringVar,
    'files:add_trailing_newline': tk.BooleanVar,
    'editing:font': tk.StringVar,
    'editing:indent': tk.IntVar,    # TODO: allow tabs? (ew)
    'editing:undo': tk.BooleanVar,
    'editing:autocomplete': tk.BooleanVar,
    'editing:color_theme': tk.StringVar,
    'gui:linenumbers': tk.BooleanVar,
    'gui:statusbar': tk.BooleanVar,
    'gui:default_geometry': tk.StringVar,
}


def _load_config(user_settings=True):
    files = [os.path.join(_here, 'default_settings.ini')]
    if user_settings:
        files.append(os.path.join(_user_config_dir, 'settings.ini'))

    temp_parser = configparser.ConfigParser()
    temp_parser.read(files)

    for string, var in config.items():
        var = config[string]
        sectionname, key = string.split(':')
        section = temp_parser[sectionname]

        if isinstance(var, tk.BooleanVar):
            var.set(section.getboolean(key))
        elif isinstance(var, tk.IntVar):
            var.set(section.getint(key))
        elif isinstance(var, tk.StringVar):
            var.set(section[key])
        else:
            raise TypeError("unexpected tkinter variable type: "
                            + type(var).__name__)


def load():
    for string, vartype in _config_info.items():
        config[string] = vartype()

    os.makedirs(os.path.join(_user_config_dir, 'themes'), exist_ok=True)
    _load_config(user_settings=True)

    color_themes.read(
        [os.path.join(_here, 'default_themes.ini')]
        + glob.glob(os.path.join(_user_config_dir, 'themes', '*.ini'))
    )


def reset_config():
    _load_config(user_settings=False)


_COMMENTS = """\
# This is a Porcupine configuration file. You can edit this manually,
# but any comments or formatting will be lost.
"""


def save():
    parser = configparser.ConfigParser()

    for string, var in config.items():
        if isinstance(var, tk.StringVar):
            value = var.get()
        elif isinstance(var, tk.BooleanVar):
            value = 'yes' if var.get() else 'no'
        elif isinstance(var, tk.IntVar):
            value = str(var.get())
        else:
            raise NotImplementedError(
                "cannot convert value of %s to configparser string"
                % type(var).__name__)

        sectionname, key = string.split(':')
        try:
            parser[sectionname][key] = value
        except KeyError:
            parser[sectionname] = {key: value}

    with open(os.path.join(_user_config_dir, 'settings.ini'), 'w') as f:
        print(_COMMENTS, file=f)
        parser.write(f)
