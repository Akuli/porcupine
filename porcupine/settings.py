import codecs
import collections.abc
import configparser
import functools
import logging
import os
import tkinter.font as tkfont
import types

from porcupine import dirs, utils

log = logging.getLogger(__name__)


# this is a custom exception because plain ValueError is often raised
# when something goes wrong unexpectedly
class InvalidValue(Exception):
    """Validators raise this when attempting to set an invalid value.

    You can also catch this to check if a value is valid::

        try:
            config['Editing', 'indent'] = new_indent_size
        except InvalidValue:
            show_error_message()
    """


class _Config(collections.abc.MutableMapping):
    """A dictionary-like object for storing settings.

    The config object behaves like a ``{(section, configkey): value}``
    dictionary where *section* and *configkey* are strings, but they
    also support things like running callbacks when something changes
    and default values. Note that ``config['key', 'value']`` does the
    same thing as ``config[('key', 'value')]``, so usually you don't
    need to use parentheses when setting or getting values.

    .. note::
        If you use threads, don't set config values from other threads
        than the main thread. Setting values may run callbacks that need
        to do something with tkinter.
    """

    def __init__(self, filename):
        self._filename = filename
        self._infos = {}    # see add_key()
        self._values = {}
        self.hooks = {}
        self.anything_changed_hook = utils.CallbackHook(__name__)

        # this is stored here to allow keeping unknown settings in the
        # setting files, this way if the user enables a plugin, disables
        # it and enables it again, the settings will be there
        self._configparser = configparser.ConfigParser()

    def connect(self, section, key, callback, run_now=False):
        """Handy way to do ``config.hooks[section, key].connect(callback)``.

        The callback will also be called right away if ``run_now`` is True.
        """
        self.hooks[section, key].connect(callback)
        if run_now:
            callback(self[section, key])
        return callback

    def disconnect(self, section, key, callback):
        """Same as ``config.hooks[section, key].disconnect(callback)``."""
        self.hooks[section, key].disconnect(callback)

    def __setitem__(self, item, value):
        info = self._infos[item]
        if info.validate is not None:
            info.validate(value)

        # make sure that the configparser isn't caching an old value
        section, key = item
        try:
            del self._configparser[section][key]
        except KeyError:
            pass

        old_value = self[item]
        self._values[item] = value
        if value != old_value:
            log.debug("%r was set to %r, running callbacks", item, value)
            self.hooks[item].run(value)
            self.anything_changed_hook.run(section, key, value)

    def __getitem__(self, item):
        # this raises KeyError
        info = self._infos[item]

        try:
            return self._values[item]
        except KeyError:
            # maybe it's loaded in the configparser, but not converted
            # to a non-string yet? this happens when plugins add their
            # own config keys after the config is loaded
            section, key = item
            try:
                string_value = self._configparser[section][key]
            except KeyError:    # nope
                self._values[item] = info.default
            else:       # it's there :D
                self._values[item] = info.from_string(string_value)
            return self._values[item]

    def __delitem__(self, item):    # the abc requires this
        raise TypeError("cannot delete setting keys")

    def __iter__(self):
        return iter(self._infos)

    def __len__(self):
        return len(self._infos)

    def add_key(self, section, configkey, default=None, *,
                converters=(str, str), validator=None, reset=True):
        """Add a new valid key to the config.

        Unlike with regular dictionaries, you need to add keys to the
        config before you can set them to a value. This method does
        that.

        ``config[section, configkey]`` will be *default* unless
        something else is specified.

        The *converters* argument should be a two-tuple of
        ``(from_string, to_string)`` functions. They should construct
        values from strings and convert them back to strings,
        respectively. Both functions are called like ``function(value)``
        and they should return the converted value.

        If a validator is given, it will be called with the new value as
        the only argument when setting a value. It may raise an
        :exc:`.InvalidValue` exception.

        If *reset* is False, :meth:`reset` won't do anything to the
        value. This is useful for things that are not controlled with
        the setting dialog, like ``pygments_style``.
        """
        # the font validators require a tkinter root window and this
        # needs to run at import time (no root window yet)
        if validator is not None and section != 'Font':
            validator(default)

        info = types.SimpleNamespace(
            default=default, validate=validator, reset=reset)
        info.from_string, info.to_string = converters
        self._infos[section, configkey] = info
        self.hooks[section, configkey] = utils.CallbackHook(__name__)

    def add_bool_key(self, section, configkey, default, **kwargs):
        """A convenience method for adding Boolean keys.

        The value is ``yes`` or ``no`` when converted to a string.
        """
        converters = (        # (from_string, to_string)
            lambda string: {'yes': True, 'no': False}.get(string, default),
            lambda boolean: ('yes' if boolean else 'no'))
        self.add_key(section, configkey, default,
                     converters=converters, **kwargs)

    def add_int_key(self, section, configkey, default, *,
                    minimum=None, maximum=None, validator=None, **kwargs):
        """A convenience method for adding integer keys.

        The *minimum* and *maximum* arguments can be used to
        automatically add a validator that makes sure that the value is
        minimum, maximum or something between them. Of course, you can
        also use a custom *validator* with or without the
        minimum-maximum validator.
        """
        def the_real_validator(value):
            if minimum is not None and value < minimum:
                raise InvalidValue("%r is too small" % value)
            if maximum is not None and value > maximum:
                raise InvalidValue("%r is too big" % value)
            if validator is not None:
                validator(value)

        self.add_key(section, configkey, default, converters=(int, str),
                     validator=the_real_validator, **kwargs)

    def reset(self, key=None):
        """Set a settings to the default value.

        The key can be a ``(section, configkey)`` tuple or None. If it's
        None, all settings will be set to defaults.
        """
        if key is None:
            for the_key, info in self._infos.items():
                if info.reset:
                    self[the_key] = info.default
        else:
            self[key] = self._infos[key].default

    def load(self):
        """Load all settings so other modules can use them.

        This must be called after creating a tkinter root window.
        """
        # the font stuff must be here because validating a font requires the
        # tkinter root window
        fixedfont = tkfont.Font(name='TkFixedFont', exists=True)
        original_family = fixedfont.actual('family')

        def on_family_changed(family):
            fixedfont['family'] = original_family if family is None else family

        def on_size_changed(size):
            fixedfont['size'] = size

        self.connect('Font', 'family', on_family_changed, run_now=True)
        self.connect('Font', 'size', on_size_changed, run_now=True)

        # now the stupid font stuff is done, time to do what this method
        # is supposed to be doing
        self._configparser.clear()
        if not self._configparser.read([self._filename]):
            # the user file can't be read, no need to do anything
            return

        for sectionname, section in self._configparser.items():
            for configkey, value in section.items():
                try:
                    info = self._infos[sectionname, configkey]
                except KeyError:
                    # see the comments about _configparser in __init__()
                    log.info("unknown config key %r", (section, configkey))
                    continue

                try:
                    self[sectionname, configkey] = info.from_string(value)
                except InvalidValue:
                    log.warning(
                        "cannot set %r to %r", (sectionname, configkey),
                        value, exc_info=True)

    def save(self):
        """Save all non-default settings to the user's file."""
        # if the user opens up two porcupines, the other porcupine might
        # have saved to the config file while this porcupine was running
        # we'll avoid overwriting its settings
        self._configparser.read([self._filename])

        for (section, configkey), value in self.items():
            info = self._infos[section, configkey]
            if value == info.default:
                # make sure the default will be used
                try:
                    del self._configparser[section][configkey]
                except KeyError:
                    pass
            else:
                string = info.to_string(value)
                try:
                    self._configparser[section][configkey] = string
                except KeyError:
                    self._configparser[section] = {configkey: string}

        # delete empty sections
        for sectionname in self._configparser.sections().copy():
            if not self._configparser[sectionname]:
                del self._configparser[sectionname]

        with open(self._filename, 'w') as file:
            self._configparser.write(file)


def _validate_encoding(name):
    try:
        codecs.lookup(name)
    except LookupError as e:
        raise InvalidValue(str(e)) from None


# this needs a tkinter root window
def _validate_font_family(family):
    if family.casefold() not in map(str.casefold, tkfont.families()):
        raise InvalidValue("unknown family %r" % family)


config = _Config(os.path.join(dirs.configdir, 'settings.ini'))
config.add_key('Font', 'family', None, validator=_validate_font_family)
config.add_int_key('Font', 'size', 10, minimum=3, maximum=1000)
config.add_key('Files', 'encoding', 'UTF-8', validator=_validate_encoding)
config.add_bool_key('Files', 'add_trailing_newline', True)
config.add_bool_key('Editing', 'undo', True)
config.add_int_key('Editing', 'indent', 4, minimum=1)
config.add_int_key('Editing', 'maxlinelen', 79, minimum=1)
config.add_key('Editing', 'pygments_style', 'default', reset=False)
config.add_key('GUI', 'default_size', '650x500')   # TODO: fix this
