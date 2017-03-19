import codecs
import configparser
import glob
import os
import pkgutil
import re
import sys
import tkinter as tk
import tkinter.font as tkfont
import traceback


# color_themes can be a configparser.ConfigParser object, but other
# settings can't be because i want the changes to be applied immediately
# when something is selected in the setting dialog. setting and getting
# other settings must also be painless because it's done in many places.
class _Config:

    def __init__(self, *, dont_reset=()):
        self.variables = {}
        self._callbacks = {}
        self._validators = {}
        self._dont_reset = dont_reset
        self.default_values = None
        self.original_values = None

    def setup(self, contentlist):
        for key, vartype, validator in contentlist:
            # The variables are named like the keys to make them easy
            # to recognize in _on_var_changed().
            var = vartype(name=key)
            var.trace('w', self._on_var_changed)
            self.variables[key] = var
            self._callbacks[key] = []
            self._validators[key] = validator

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

        for key in self.keys():
            if not self.validate(key, self[key]):
                print("%s: invalid %r value %r, using %r instead"
                      % (__name__, key, self[key], self.default_values[key]),
                      file=sys.stderr)
                self[key] = self.default_values[key]

    def _configparser_load(self, parser, allow_missing=False):
        for key, var in self.variables.items():
            sectionname, configkey = key.split(':')
            try:
                section = parser[sectionname]
                section[configkey]
            except KeyError as e:
                if allow_missing:
                    continue
                raise e

            if isinstance(var, tk.BooleanVar):
                var.set(section.getboolean(configkey))
            elif isinstance(var, tk.IntVar):
                var.set(section.getint(configkey))
            elif isinstance(var, tk.StringVar):
                var.set(section[configkey])
            else:
                raise TypeError(type(var).__name__)

    def dump(self, file):
        parser = configparser.ConfigParser()
        for string, var in self.variables.items():
            if var.get() == self.default_values[string]:
                continue

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

    # rest of this is mostly convenience stuff
    def connect(self, string, callback):
        self._callbacks[string].append(callback)

    def validate(self, string, value):
        validator = self._validators[string]
        return validator is None or validator(value)

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


def _validate_encoding(name):
    try:
        codecs.lookup(name)
        return True
    except LookupError:
        return False


def _validate_geometry(geometry):
    """Check if a tkinter geometry is valid.

    >>> _validate_geometry('100x200+300+400')
    True
    >>> _validate_geometry('100x200')
    True
    >>> _validate_geometry('+300+400')
    True
    >>> _validate_geometry('asdf')
    False
    >>> # tkinter actually allows '', but it does nothing
    >>> _validate_geometry('')
    False
    """
    if not geometry:
        return False
    return re.search(r'^(\d+x\d+)?(\+\d+\+\d+)?$', geometry) is not None


def _validate_fontstring(string):
    if string == 'TkFixedFont':
        # special case, but this is case-sensitive here because tkinter
        # wants it CapsWordy
        return True

    match = re.search(r'^\{(.+)\} (\d+)$', string)
    if match is None or int(match.group(2)) <= 0:
        return False
    return match.group(1).casefold() in map(str.casefold, tkfont.families())


def load():
    os.makedirs(os.path.join(_user_config_dir, 'themes'), exist_ok=True)

    # color themes must be read first because the editing:color_theme
    # validator needs it
    default_themes = pkgutil.get_data('porcupine', 'default_themes.ini')
    color_themes.read_string(default_themes.decode('utf-8'))
    escaped_path = glob.escape(os.path.join(_user_config_dir, 'themes'))
    color_themes.read(glob.glob(os.path.join(escaped_path, '*.ini')))

    # we can't create StringVar etc. earlier because they need a root window
    # TODO: allow tabs? (ew)
    config.setup([
        # (string, vartype, validator)
        ('files:encoding', tk.StringVar, _validate_encoding),
        ('files:add_trailing_newline', tk.BooleanVar, None),
        ('editing:font', tk.StringVar, _validate_fontstring),
        ('editing:indent', tk.IntVar, (lambda value: value > 0)),
        ('editing:undo', tk.BooleanVar, None),
        ('editing:autocomplete', tk.BooleanVar, None),
        ('editing:color_theme', tk.StringVar,
         (lambda name: name in color_themes)),
        ('gui:linenumbers', tk.BooleanVar, None),
        ('gui:statusbar', tk.BooleanVar, None),
        ('gui:default_geometry', tk.StringVar, _validate_geometry),
    ])

    default_config = pkgutil.get_data('porcupine', 'default_settings.ini')
    config.load(default_config.decode('utf-8'),
                os.path.join(_user_config_dir, 'settings.ini'))


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
