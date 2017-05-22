"""Setting manager for Porcupine."""
# TODO: currently the settings are a mess :( i have turned many things
# into plugins, and the plugins use random config values from different
# config sections and it's not organized in any way

import collections
import configparser
import contextlib
import logging
import os

from porcupine import dirs, utils

log = logging.getLogger(__name__)


class InvalidValue(Exception):
    """Raised when attempting to set an invalid value."""


class _Config(configparser.ConfigParser):
    """Like :class:`configparser.ConfigParser`, but supports callbacks.

    When a value is set, the config object does these things:

    1. The value is converted to a string with `str()` because
       configparser only handles strings.
    2. Validator callbacks are called. If one of them returns False,
       :exc:`~InvalidValue` is raised and the setting process stops.
    3. The value is set normally.
    4. Each callback added with :meth:`~connect` is called with the new
       value.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # these are like {(sectionname, key): valuelist}
        self._validators = collections.defaultdict(list)
        self._callbacks = collections.defaultdict(list)

    # currently configparser always calls this method, i'll add more
    # overrides if future versions of it stop doing that. the docstring
    # says that configparser.ConfigParser.set "extends
    # RawConfigParser.set by validating type and interpolation syntax on
    # the value", so maybe this isn't an implementation detail :^)
    def set(self, section, key, value):
        value = str(value)
        for validator in self._validators[(section, key)]:
            if not validator(value):
                raise InvalidValue("%s(%r) returned False" % (
                    utils.nice_repr(validator), value))

        try:
            old_value = self[section][key]
        except KeyError:
            old_value = object()    # run the changed callbacks
        super().set(section, key, value)
        new_value = self[section][key]

        if old_value != new_value:
            log.info("setting %s:%s to %r", section, key, new_value)
            for callback in self._callbacks[(section, key)]:
                callback(new_value)

    @contextlib.contextmanager
    def _disconnecter(self, section, key, callback):
        try:
            yield
        finally:
            self.disconnect(section, key, callback)

    def connect(self, section, key, callback=None, *, run_now=True):
        """Run ``callback(new_value)`` when a setting changes.

        If *run_now* is True, *callback* will also be ran right away
        when this function is called. This function returns an object
        that can be used as a context manager for disconnecting the
        callback easily::

            def cool_callback(value):
                ...

            with config.connect('some_section:some_key', cool_callback):
                # do something here

        The connect method can be used as a decorator too, but the
        disconnecter will be lost::

            @config.connect('some_section:some_key')
            def cool_callback(value):
                ...

            try:
                # do something here
            finally:
                config.disconnect('some_section:some_key', cool_callback)
        """
        if callback is None:
            def decorated(callback):
                self.connect(section, key, callback, run_now=run_now)
                return callback
            return decorated

        self._callbacks[(section, key)].append(callback)
        if run_now:
            callback(self[section][key])
        return self._disconnecter(section, key, callback)

    def disconnect(self, section, key, callback):
        """Undo a :meth:`~connect` call."""
        self._callbacks[(section, key)].remove(callback)

    def validator(self, section, key):
        """A decorator that adds a validator function.

        The validator will be called with the new value converted to a
        string as its only argument, and it should return True if the
        value is OK.
        """
        def validator_adder(function):
            self._validators.setdefault((section, key), []).append(function)
            return function
        return validator_adder

    def to_dict(self):
        """Convert the config object to nested dictionaries."""
        return {name: dict(section) for name, section in self.items()}


color_themes = configparser.ConfigParser(default_section='Default')
config = _Config()
_saved_config = {}

_default_config_file = os.path.join(dirs.installdir, 'default_config.ini')
_default_theme_file = os.path.join(dirs.installdir, 'default_themes.ini')
_user_config_file = os.path.join(dirs.configdir, 'settings.ini')
_user_theme_file = os.path.join(dirs.configdir, 'themes.ini')


def load():
    # these must be read first because config's editing:color_theme
    # validator needs it
    color_themes.read([_default_theme_file, _user_theme_file])
    config.read([_default_config_file, _user_config_file])
    _saved_config.clear()
    _saved_config.update(config.to_dict())


_comments = '''\
# This is a Porcupine setting file. You can edit it yourself or you can
# use Porcupine's setting dialog.
'''


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
    if config.to_dict() == _saved_config:
        log.info("config hasn't changed, not saving it")
    else:
        log.info("saving config to '%s'", _user_config_file)
        with open(_user_config_file, 'w') as f:
            print(_comments, file=f)
            config.write(f)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
