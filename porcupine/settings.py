import configparser
import glob
import os
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
    'files:encoding': str,
    'files:add_trailing_newline': bool,
    'editing:font': str,
    'editing:indent': int,    # TODO: allow tabs? (ew)
    'editing:undo': bool,
    'editing:autocomplete': bool,
    'editing:color_theme': str,
    'gui:linenumbers': bool,
    'gui:statusbar': bool,
    'gui:default_geometry': str,
}


def load():
    os.makedirs(os.path.join(_user_config_dir, 'themes'), exist_ok=True)

    color_themes.read(
        [os.path.join(_here, 'default_themes.ini')]
        + glob.glob(os.path.join(_user_config_dir, 'themes', '*.ini'))
    )

    temp_parser = configparser.ConfigParser()
    temp_parser.read([
        os.path.join(_here, 'default_settings.ini'),
        os.path.join(_user_config_dir, 'settings.ini'),
    ])

    for string, vartype in _config_info.items():
        sectionname, key = string.split(':')
        section = temp_parser[sectionname]

        if vartype == str:
            var = tk.StringVar()
            var.set(section[key])
        elif vartype == bool:
            var = tk.BooleanVar()
            var.set(section.getboolean(key))
        elif vartype == int:
            var = tk.IntVar()
            var.set(section.getint(key))
        else:
            raise NotImplementedError(
                "can't create tkinter variable of %s" % vartype.__name__)
        config[string] = var


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
