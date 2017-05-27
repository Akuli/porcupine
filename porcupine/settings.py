import collections.abc
import configparser
import functools
import logging
import os
import types

from porcupine import dirs, utils

log = logging.getLogger(__name__)


# this is a custom exception because plain ValueError is often raised
# when something goes wrong unexpectedly
class InvalidValue(ValueError):
    """This is raised when attempting to set an invalid value.

    Validator functions can raise this.
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

        # this is stored here to allow keeping unknown settings in the
        # setting files, this way if the user enables a plugin, disables
        # it and enables it again, the settings will be there
        self._configparser = configparser.ConfigParser()

        #: A dictionary with ``(section, configkey)`` tuples as keys and 
        #: :class:`..utils.CallbackHook` objects as values. The
        #: approppriate callback hook is ran when a value is set with
        #: the new value as the only argument.
        #:
        #: .. seealso::
        #:      Usually it's easiest to use the :meth:`~connect` and
        #:      :meth:`~disconnect` methods instead of using this
        #:      dictionary directly.
        self.hooks = {}

        #: Like the callback hooks in :attr:`~hooks`, but this hook is
        #: ran like ``callback(section, configkey, value)`` when any
        #: value is set.
        self.anything_changed_hook = utils.CallbackHook(__name__)

    def connect(self, section, configkey, function, run_now=False):
        """Same as ``config.hooks[section, configkey].connect(function)``.

        The function will also be called right away if ``run_now`` is True.
        """
        self.hooks[section, configkey].connect(function)
        if run_now:
            function(self[section, configkey])
        return function

    def disconnect(self, section, configkey, *args, **kwargs):
        """Same as ``config.hooks[section, configkey].disconnect``."""
        self.hooks[section, configkey].disconnect(*args, **kwargs)

    def __setitem__(self, item, value):
        info = self._infos[item]
        if info.validate is not None:
            info.validate(value)

        # make sure that the configparser isn't caching an old value
        section, configkey = item
        try:
            del self._configparser[section][configkey]
        except KeyError:
            pass

        old_value = self[item]
        self._values[item] = value
        if value != old_value:
            log.debug("%r was set to %r, running callbacks", item, value)
            self.hooks[item].run(value)
            self.anything_changed_hook.run(section, configkey, value)

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
        """Add a new valid key to a section in the config.

        ``config[section, configkey]`` will be *default* unless
        something else is specified.

        The *converters* argument should be a two-tuple of
        ``(from_string, to_string)`` functions that will be called when
        the settings are loaded and saved. These functions will be
        called with exactly one argument and they should construct the
        values from strings and convert them back to strings.

        If a validator is given, it will be called with the new value as
        the only argument when setting a value. It may raise an
        :exc:`.InvalidValue` exception.

        If *reset* is False, :meth:`reset` won't do anything to the
        value. This is useful for things that are not controlled with
        the setting dialog, like the current color theme.

        .. seealso::
            The :meth:`add_bool_key` and :meth:`add_int_key` make adding
            booleans and integers easy.
        """
        info = types.SimpleNamespace(default=default, validate=validator)
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
                    minimum=None, maximum=None, **kwargs):
        """A convenience method for adding integer keys.

        The *minimum* and *maximum* arguments can be used to
        automatically add a validator that makes sure that the value is
        minimum, maximum or something between them.
        """
        def validator(value):
            if minimum is not None and value < minimum:
                raise InvalidValue("%r is too small" % value)
            if maximum is not None and valie > maximum:
                raise InvalidValue("%r is too big" % value)

        self.add_key(section, configkey, default,
                     converters=(int, str), validator=validator, **kwargs)

    def reset(self):
        """Set all settings to defaults."""
        for key, info in self._infos.items():
            if info.reset:
                self[key] = info.default

    def load(self):
        """Read the settings from the user's file."""
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
                self[sectionname, configkey] = info.from_string(value)

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
                    if self._configparser[section][configkey] == string:
                        # the value hasn't changed
                        continue
                except KeyError:
                    pass

                # set string to config, create a new section if needed
                self._configparser.setdefault(section, {})[configkey] = string

        # delete empty sections
        for sectionname in self._configparser.sections().copy():
            if not self._configparser[sectionname]:
                del self._configparser[sectionname]

        with open(self._filename, 'w') as file:
            self._configparser.write(file)


config = _Config(os.path.join(dirs.configdir, 'settings.ini'))
config.add_key('Files', 'encoding', 'utf-8')
config.add_bool_key('Files', 'add_trailing_newline', True)
config.add_bool_key('Editing', 'undo', True)
config.add_int_key('Editing', 'indent', 4, minimum=1)
config.add_int_key('Editing', 'maxlinelen', 79, minimum=1)
config.add_key('Editing', 'color_theme', 'Default')
config.add_key('Font', 'family', '')   # see textwidget.init_font()
config.add_int_key('Font', 'size', 10, minimum=3)
config.add_key('GUI', 'default_size', '650x500')   # TODO: fix this

# color_themes can be simpler because it's never edited on the fly
color_themes = configparser.ConfigParser(default_section='Default')
color_themes.load = functools.partial(color_themes.read, [
    os.path.join(dirs.installdir, 'default_themes.ini'),
    os.path.join(dirs.configdir, 'themes.ini'),
])
