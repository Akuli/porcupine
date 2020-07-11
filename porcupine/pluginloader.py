"""Loads plugins from ``porcupine.plugins``."""
# many things are wrapped in try/except here to allow writing Porcupine
# plugins using Porcupine, so Porcupine must run if the plugins are
# broken

import importlib
import logging
import pkgutil
import random
import time
import typing

import toposort     # type: ignore

from porcupine.plugins import __path__ as plugin_paths

log = logging.getLogger(__name__)


def find_plugins() -> typing.Set[str]:
    """Return names of plugins that can be loaded.

    Note that loading some of the returned plugins may fail.
    """
    return {
        name for finder, name, is_pkg in pkgutil.iter_modules(plugin_paths)
        if not name.startswith('_')
    }


_loaded_names: typing.List[str] = []


def load(plugin_names: typing.Iterable[str], shuffle: bool = False) -> None:
    """Load plugins.

    The plugins are always ordered using their ``setup_before`` and
    ``setup_after`` lists. The *shuffle* argument determines what is
    done when multiple plugins can be loaded in any order with respect
    to each other. By default, they are sorted alphabetically, so
    things like menu items are always in the same order. Setting
    ``shuffle=True`` means that a random order is used instead; this is
    useful for making sure that the plugins don't rely on the sorting.

    Any exceptions from the plugins are caught and logged, so there's no
    need to wrap calls to this function in ``try,except``.
    """
    assert not _loaded_names, "cannot load() twice"

    plugin_infos = {}    # {name: (setup_before, setup_after, setup_func)}
    for name in plugin_names:
        log.debug("trying to import plugin: %s", name)
        start = time.time()
        try:
            module: typing.Any = importlib.import_module(
                'porcupine.plugins.' + name)
            setup_before: typing.Set[str] = set(
                getattr(module, 'setup_before', []))
            setup_after: typing.Set[str] = set(
                getattr(module, 'setup_after', []))
            setup: typing.Callable[[], None] = module.setup
        except Exception:
            log.exception("problem with importing %s", name)
            continue

        duration = time.time() - start
        log.debug("imported %s in %.3f milliseconds", name, duration*1000)

        # now we know that the plugin is ok, we can add its stuff to
        # dependencies and setup_funcs
        plugin_infos[name] = (setup_before, setup_after, setup)

    # setup_before and setup_after may contain names of plugins that are
    # not installed because they are for controlling the loading order,
    # not for requiring dependencies

    dependencies: typing.Dict[str, typing.Set[str]] = {
        name: set() for name in plugin_infos
    }
    for name, (setup_before, setup_after, setup) in plugin_infos.items():
        dependencies[name].update(setup_after & plugin_infos.keys())
        for reverse_dependency in (setup_before & plugin_infos.keys()):
            dependencies[reverse_dependency].add(name)

    # the toposort will partially work even if there's a circular
    # dependency, the CircularDependencyError is raised after doing
    # everything possible (see source code)
    loading_order: typing.List[str] = []
    try:
        # map(list, ...) doesn't work in mypy
        make_list: typing.Callable[
            [typing.Iterable[str]], typing.List[str]] = list
        for names in map(make_list, toposort.toposort(dependencies)):
            if shuffle:
                random.shuffle(names)
            else:
                names.sort()
            loading_order.extend(names)
    except toposort.CircularDependencyError as e:
        parts = ("%s depends on %s" % item for item in e.data.items())
        log.error("circular dependency: %s", ', '.join(parts))

    for name in loading_order:
        *junk, setup = plugin_infos[name]

        start = time.time()
        try:
            setup()
            _loaded_names.append(name)
        except Exception:
            log.exception("%s.setup() doesn't work", name)

        duration = time.time() - start
        log.debug("ran %s.setup() in %.3f milliseconds", name, duration*1000)


def get_loaded_plugins() -> typing.List[str]:
    """Return a list of plugin names that have been loaded successfully.

    This is useful for writing plugins that need to start a new Porcupine
    process and load the same plugins in the new process. See
    :source:`porcupine/plugins/poppingtabs.py` for an example.

    The returned list is in loading order, and mutating the returned list
    doesn't break anything.
    """
    # TODO: test the mutating thing
    return _loaded_names.copy()
