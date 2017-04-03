"""Setting manager for Porcupine."""
# TODO: currently the settings are a mess :( i have turned many things
# into plugins, and the plugins use random config values from different
# config sections and it's not organized in any way

import codecs
import collections
import configparser
import glob
import json
import logging
import os
import pkgutil
import re
import tkinter.font as tkfont

from porcupine import dirs

log = logging.getLogger(__name__)


class _Config:
    """A {'section:name': value} dictionary-like object.

    Unlike plain dictionaries, these objects support things like
    callbacks that run when a value is changed.

    >>> c = _Config({})
    >>> c.load({'test': {'a': 1, 'b': 2}}, {'test': {'a': 3}})
    >>> dict(c) == {'test:a': 3, 'test:b': 2}
    True
    >>> c['test:b']     # default setting
    2
    >>> c['test:a']     # user setting that overrides a default setting
    3
    >>> c.dump()        # settings that are different from defaults
    {'test': {'a': 3}}
    >>>
    """

    def __init__(self, name, validators=None):
        if validators is None:
            validators = {}
        self.log = logging.getLogger(name)
        self._validators = validators
        self._callbacks = collections.defaultdict(list)
        self._default_values = None
        self._original_values = None
        self._values = None

    def _flatten_dict(self, dictionary):
        result = {}
        for key1, sub in dictionary.items():
            for key2, value in sub.items():
                result[key1 + ':' + key2] = value
        return result

    def _unflatten_dict(self, dictionary):
        result = {}
        for key, value in dictionary.items():
            key1, key2 = key.split(':')
            try:
                result[key1][key2] = value
            except KeyError:
                result[key1] = {key2: value}
        return result

    def load(self, defaults, user_settings):
        """Set settings from two dict-like objects."""
        self._values = self._flatten_dict(defaults)
        self._default_values = self._values.copy()

        # the user setting dict can contain more or less values than the
        # default dict if we're using a config file from an older or
        # newer porcupine, but it doesn't matter
        user_settings = self._flatten_dict(user_settings)
        for key in self.keys() & user_settings.keys():
            value = user_settings[key]
            if self.validate(key, value):
                self[key] = value
            else:
                self.log.warning("invalid %r value %r, using %r instead",
                                 key, value, self[key])
        self._original_values = dict(self)

    def dump(self):
        result = {}
        for key in self.keys():
            if self[key] != self._default_values[key]:
                result[key] = self[key]
        return self._unflatten_dict(result)

    def needs_saving(self):
        return dict(self) != self._original_values

    def reset(self):
        for key in self.keys():
            self[key] = self._default_values[key]

    def validate(self, key, value):
        assert key in self.keys()
        try:
            validator = self._validators[key]
        except KeyError:
            return True
        return validator(value)

    def connect(self, key, callback):
        self._callbacks[key].append(callback)

    def disconnect(self, key, callback):
        self._callbacks[key].remove(callback)

    def __setitem__(self, key, new_value):
        assert self.validate(key, new_value)
        if isinstance(key, tuple):
            # config['section', 'key'] -> config['section:key']
            key = ':'.join(key)

        old_value = self[key]
        self._values[key] = new_value
        if old_value != new_value:
            self.log.info("setting %r to %r", key, new_value)
            for callback in self._callbacks[key]:
                callback(key, new_value)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            key = ':'.join(key)
        return self._values[key]

    # this is used by dict(some_config_object)
    def keys(self):
        return self._default_values.keys()

    def sections(self):
        result = set()
        for key in self.keys():
            result.add(key.split(':')[0])
        return result


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
        # tkinter's default font, doesn't support specifying a size
        return True

    match = re.search(r'^\{(.+)\} (\d+)$', string)
    if match is None or int(match.group(2)) <= 0:
        return False
    return match.group(1).casefold() in map(str.casefold, tkfont.families())


color_themes = _Config('porcupine.settings.color_themes')
config = _Config('porcupine.settings.config', {
    'files:encoding': _validate_encoding,
    'editing:font': _validate_fontstring,
    'editing:indent': (lambda value: value > 0),
    'editing:color_theme': (lambda name: name in color_themes.sections()),
    'editing:maxlinelen': (lambda value: value > 0),
    'gui:default_geometry': _validate_geometry,
})

_user_config_file = os.path.join(dirs.configdir, 'settings.json')
_theme_glob = os.path.join(glob.escape(dirs.themedir), '*.ini')


def _configparser2dict(parser):
    """Copy a config parser into a dictionary."""
    result = {}
    for sectionname, section in parser.items():
        result[sectionname] = dict(section)
    return result


def load():
    os.makedirs(dirs.themedir, exist_ok=True)

    # these must be read first because config's editing:color_theme
    # validator needs it
    themebytes = pkgutil.get_data('porcupine', 'default_themes.ini')
    parser = configparser.ConfigParser(default_section='Default')
    parser.read_string(themebytes.decode('utf-8'))
    default_themes = _configparser2dict(parser)

    for nondefaultsectionname in parser.sections():
        del parser[nondefaultsectionname]
    parser.read(glob.glob(_theme_glob))
    user_themes = _configparser2dict(parser)

    color_themes.load(default_themes, user_themes)

    default_config = json.loads(
        pkgutil.get_data('porcupine', 'default_config.json').decode('ascii'))

    try:
        with open(_user_config_file, 'r') as f:
            user_config = json.load(f)
    except FileNotFoundError:
        log.info("user-wide setting file '%s' was not found, " +
                 "using default settings", _user_config_file)
        user_config = {}
    except Exception:
        log.exception("unexpected error while reading settings from '%s'",
                      _user_config_file)
        user_config = {}

    config.load(default_config, user_config)


def save():
    # It's important to check if the config changed because otherwise:
    #  1. The user opens up two Porcupines. Let's call them A and B.
    #  2. The user changes settings in porcupine A.
    #  3. The user closes Porcupine A and it saves the settings.
    #  4. The user closes Porcupine B and it overwrites the settings
    #     that A saved.
    #  5. The user opens up Porcupine again and the settings are gone.
    #
    # Of course, this doesn't handle the user changing settings in
    # both Porcupines, but I think it's not too bad to assume that
    # most users don't do that.
    if config.needs_saving():
        log.info("saving config to '%s'", _user_config_file)
        with open(_user_config_file, 'w') as file:
            json.dump(config.dump(), file, indent=4)
            file.write('\n')
    else:
        log.info("config hasn't changed, not saving it")


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
