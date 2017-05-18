"""Loads plugins from :mod:`porcupine.plugins`."""
# TODO: add some way to require setting up another plugin before loading
#       some particular plugin

import importlib
import logging
import os
import random

from porcupine import dirs, plugins

log = logging.getLogger(__name__)


# these are wrapped tightly in try/except because someone might write
# Porcupine plugins using Porcupine, so Porcupine must run if the
# plugins are broken
def load(editor):
    modulenames = []
    for path in plugins.__path__:
        for name, ext in map(os.path.splitext, os.listdir(path)):
            if name.isidentifier() and name[0] != '_' and ext == '.py':
                modulenames.append('porcupine.plugins.' + name)
    log.info("found %d plugins", len(modulenames))

    # plugins should be made so that their loading order doesn't matter,
    # so let's heavily discourage relying on it :D
    random.shuffle(modulenames)

    for name in modulenames:
        try:
            module = importlib.import_module(name)
            module.setup(editor)
        except Exception:
            log.exception("problem with loading %s", name)
        else:
            log.info("successfully loaded %s", name)
