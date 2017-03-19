import configparser
import glob
import os
import pkgutil
import tkinter as tk
import traceback


# color_themes can be a configparser.ConfigParser object, but other
# settings can't be because i want the changes to be applied immediately
# when something is selected in the setting dialog. setting and getting
# other settings must also be painless because it's done in many places.
class _Config:

    def __init__(self, *, dont_reset=()):
        self.variables = {}   # see setup()
        self._callbacks = {}  # see setup() and _on_var_changed()
        self._dont_reset = dont_reset
        self.default_values = None
        self.original_values = None

    def setup(self, contentlist):
        for string, vartype in contentlist:
            # The variables are named like the strings to make them easy
            # to recognize in _on_var_changed().
            var = vartype(name=string)
            var.trace('w', self._on_var_changed)
            self.variables[string] = var
            self._callbacks[string] = []

    def _on_var_changed(self, key, *junk):
        try:
            value = self.variables[key].get()
            for callback in self._callbacks[key]:
                callback(key, value)
        except Exception:  # tkinter suppresses these exceptions :(
            traceback.print_exc()

    def load(self, defaultstring, userfile):
        parser = configparser.ConfigParser()
        parser.read_string(defaultstring)
        self._configparser_load(parser)
        self.default_values = dict(self)

        parser = configparser.ConfigParser()
        if parser.read([userfile]):
            self._configparser_load(parser, allow_missing=True)
        self.original_values = dict(self)

    def _configparser_load(self, parser, allow_missing=False):
        for string, var in self.variables.items():
            sectionname, key = string.split(':')
            try:
                section = parser[sectionname]
                section[key]
            except KeyError as e:
                if allow_missing:
                    continue
                raise e

            if isinstance(var, tk.BooleanVar):
                var.set(section.getboolean(key))
            elif isinstance(var, tk.IntVar):
                var.set(section.getint(key))
            elif isinstance(var, tk.StringVar):
                var.set(section[key])
            else:
                raise TypeError(type(var).__name__)

    def dump(self, file):
        parser = configparser.ConfigParser()
        for string, var in self.variables.items():
            if isinstance(var, tk.StringVar):
                value = var.get()
            elif isinstance(var, tk.BooleanVar):
                value = 'yes' if var.get() else 'no'
            elif isinstance(var, tk.IntVar):
                value = str(var.get())
            else:
                raise TypeError("can't convert to configparser string: "
                                + type(var).__name__)

            sectionname, key = string.split(':')
            try:
                parser[sectionname][key] = value
            except KeyError:
                parser[sectionname] = {key: value}

        parser.write(file)

    def reset(self):
        for name in self.keys():
            if name not in self._dont_reset:
                self[name] = self.default_values[name]

    # rest of this is convenience stuff
    def connect(self, string, callback):
        self._callbacks[string].append(callback)

    def __setitem__(self, string, value):
        self.variables[string].set(value)

    def __getitem__(self, string):
        return self.variables[string].get()

    # allow calling dict() on this
    def keys(self):
        return iter(self.variables)


color_themes = configparser.ConfigParser(default_section='Default')
config = _Config(dont_reset=['editing:color_theme'])
_user_config_dir = os.path.join(os.path.expanduser('~'), '.porcupine')


def load():
    os.makedirs(os.path.join(_user_config_dir, 'themes'), exist_ok=True)

    # we can't create StringVar etc. earlier because they need a root window
    config.setup([
        # (string, vartype)
        ('files:encoding', tk.StringVar),
        ('files:add_trailing_newline', tk.BooleanVar),
        ('editing:font', tk.StringVar),
        ('editing:indent', tk.IntVar),     # TODO: allow tabs? (ew)
        ('editing:undo', tk.BooleanVar),
        ('editing:autocomplete', tk.BooleanVar),
        ('editing:color_theme', tk.StringVar),
        ('gui:linenumbers', tk.BooleanVar),
        ('gui:statusbar', tk.BooleanVar),
        ('gui:default_geometry', tk.StringVar),
    ])

    default_config = pkgutil.get_data('porcupine', 'default_settings.ini')
    config.load(default_config.decode('utf-8'),
                os.path.join(_user_config_dir, 'settings.ini'))

    default_themes = pkgutil.get_data('porcupine', 'default_themes.ini')
    color_themes.read_string(default_themes.decode('utf-8'))
    escaped_path = glob.escape(os.path.join(_user_config_dir, 'themes'))
    color_themes.read(glob.glob(os.path.join(escaped_path, '*.ini')))


_COMMENTS = """\
# This is a Porcupine configuration file. You can edit this manually,
# but any comments or formatting will be lost.
"""


def save():
    # It's important to check if the config changed because otherwise:
    #  1. The user opens up two Porcupines. Let's call them A and B.
    #  2. The user changes settings in porcupine A.
    #  3. The user closes Porcupine A and it saves the settings.
    #  4. The user closes Porcupine B and it overwrites the settings
    #     that A saved.
    #  5. The user opens up Porcupine again and the settings are gone.
    # Of course, this doesn't handle the user changing settings in
    # both Porcupines, but I think it's not too bad to assume that
    # most users don't do that.
    if dict(config) != config.original_values:
        with open(os.path.join(_user_config_dir, 'settings.ini'), 'w') as f:
            print(_COMMENTS, file=f)
            config.dump(f)
