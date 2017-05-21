"""Loads plugins from :mod:`porcupine.plugins`."""
# many things are wrapped in try/except here to allow writing Porcupine
# plugins using Porcupine, so Porcupine must run if the plugins are
# broken

from collections import namedtuple
import importlib
import logging
import os
import random

import porcupine.plugins

log = logging.getLogger(__name__)

Plugin = namedtuple('Plugin', 'name setup setup_after')


# plugins must be loaded exactly once in the correct order, so we need
# to store state and a class makes sense
class PluginLoader:

    def __init__(self, editor, plugins):
        self._editor = editor
        self._all_plugins = {}
        self._states = {}
        for plugin in plugins:
            self._all_plugins[plugin.name] = plugin
            self._states[plugin.name] = 'waiting'

    def _raw_load(self, plugin):
        log.debug("running %s.setup", plugin.name)
        try:
            plugin.setup(self._editor)
        except Exception:
            log.exception("%s.setup doesn't work", plugin.name)

    def load(self, name):
        if self._states[name] == 'loaded':
            return

        assert self._states[name] == 'waiting'
        self._states[name] = 'loading'

        plugin = self._all_plugins[name]
        for load_this_first in plugin.setup_after:
            if load_this_first not in self._all_plugins:
                continue

            if load_this_first == name:
                raise ValueError("%r has itself in the setup_after list"
                                 % name)
            if self._states[load_this_first] == 'loading':
                # they need to be loaded before each other directly or
                # indirectly
                # example of conflicting indirectly: A requires B,
                # B requires C, C requires A
                raise ValueError(
                    "%r and %r have conflicting setup_after lists"
                    % (name, load_this_first))
            self.load(load_this_first)

        self._raw_load(plugin)
        self._states[name] = 'loaded'


def load(editor, shuffle):
    modulenames = []
    for path in porcupine.plugins.__path__:
        # this handles directories and files
        for name, ext in map(os.path.splitext, os.listdir(path)):
            if name.isidentifier() and not name.startswith('_'):
                modulenames.append('porcupine.plugins.' + name)
    log.info("found %d plugins", len(modulenames))

    if shuffle:
        random.shuffle(modulenames)
    else:
        modulenames.sort()

    plugins = []
    for name in modulenames:
        log.debug("importing %s", name)
        try:
            module = importlib.import_module(name)
            setup_after = {
                'porcupine.plugins.' + name
                for name in getattr(module, 'setup_after', [])
            }
            plugins.append(Plugin(
                name=name, setup=module.setup,
                setup_after=setup_after,
            ))
        except Exception:
            log.exception("problem with importing %s", name)

    # modulenames contains modules that failed to import, must not use
    # it here
    loader = PluginLoader(editor, plugins)
    for plugin in plugins:
        loader.load(plugin.name)
