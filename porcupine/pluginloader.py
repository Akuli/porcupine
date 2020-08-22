"""Loads plugins from ``porcupine.plugins``."""
# many things are wrapped in try/except here to allow writing Porcupine
# plugins using Porcupine, so Porcupine must run if the plugins are
# broken

import argparse
import dataclasses
import enum
import importlib.machinery
import logging
import pkgutil
import random
import time
import traceback
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

import toposort     # type: ignore

from porcupine import settings
from porcupine.plugins import __path__ as plugin_paths

log = logging.getLogger(__name__)


class Status(enum.Enum):
    """
    This :mod:`Enum <enum>` represents the status of the plugin in the
    currently running Porcupine process.

    .. data:: LOADING

        The plugin hasn't been set up successfully yet, but no errors
        preventing the setup have occurred.

    .. data:: ACTIVE

        The plugin was imported and its ``setup()`` function was called successfully.

    .. data:: DISABLED_BY_SETTINGS

        The plugin wasn't loaded because it's in the ``disabled_plugins``
        setting. See :mod:`porcupine.settings`.

    .. data:: DISABLED_ON_COMMAND_LINE

        The plugin wasn't loaded because it was listed in a
        ``--without-plugins`` argument given to Porcupine.

    .. data:: IMPORT_FAILED

        Importing the plugin raised an error.

    .. data:: SETUP_FAILED

        The plugin was imported successfully, but calling its ``setup()``
        function raised an error.

    .. data:: CIRCULAR_DEPENDENCY_ERROR

        Plugins with this status were imported, but their ``setup_before`` and
        ``setup_after`` lists make it impossible to determine the correct order
        for calling their ``setup()`` function. For example, if plugin *A*
        should be set up before *B*, *B* should be set up before *C* and *C*
        should be set up before *A*, then *A*, *B* and *C* will all fail with
        ``CIRCULAR_DEPENDENCY_ERROR``.
    """
    LOADING = enum.auto()    #: bla
    ACTIVE = enum.auto()    #: bla
    DISABLED_BY_SETTINGS = enum.auto()    #: bla
    DISABLED_ON_COMMAND_LINE = enum.auto()    #: bla
    IMPORT_FAILED = enum.auto()    #: bla
    SETUP_FAILED = enum.auto()    #: bla
    CIRCULAR_DEPENDENCY_ERROR = enum.auto()    #: bla


@dataclasses.dataclass
class PluginInfo:
    """
    This :mod:`dataclass <dataclasses>` represents a plugin.

    It's usually better to use ``info.setup_before``
    instead of accessing ``info.module.setup_before`` directly.
    Not all plugins define a ``setup_before`` variable, and if it's not present,
    then ``info.setup_before`` is an empty set.
    This also applies to ``setup_after``.

    The value of *error* depends on *status*:

        * If *status* is ``LOADING``, ``ACTIVE``, ``DISABLED_BY_SETTINGS`` or
          ``DISABLED_ON_COMMAND_LINE``, then *error* is ``None``.
        * If *status* is ``IMPORT_FAILED`` or ``SETUP_FAILED``, then *error*
          is a Python error message, starting with
          ``Traceback (most recent call last):``.
        * If *status* is ``CIRCULAR_DEPENDENCY_ERROR``, then *error* is a
          user-readable one-line message.
    """
    name: str
    came_with_porcupine: bool
    status: Status
    module: Optional[Any]
    setup_before: Set[str]
    setup_after: Set[str]
    error: Optional[str]


_mutable_plugin_infos: List[PluginInfo] = []
plugin_infos: Sequence[PluginInfo] = _mutable_plugin_infos  # changing content is mypy error


def _did_plugin_come_with_porcupine(finder: object) -> bool:
    return isinstance(finder, importlib.machinery.FileFinder) and finder.path == plugin_paths[-1]


# undocumented on purpose, don't use in plugins
def import_plugins(disabled_on_command_line: List[str]):
    assert not _mutable_plugin_infos
    _mutable_plugin_infos.extend(
        PluginInfo(
            name=name,
            came_with_porcupine=_did_plugin_come_with_porcupine(finder),
            status=Status.LOADING,
            module=None,
            setup_before=set(),
            setup_after=set(),
            error=None,
        )
        for finder, name, is_pkg in pkgutil.iter_modules(plugin_paths)
        if not name.startswith('_')
    )

    for info in _mutable_plugin_infos:
        # If it's disabled in settings and on command line, then status is set
        # to DISABLED_BY_SETTINGS. This makes more sense for the user of the
        # plugin manager dialog.
        if info.name in settings.get('disabled_plugins', List[str]):
            info.status = Status.DISABLED_BY_SETTINGS
            continue
        if info.name in disabled_on_command_line:
            info.status = Status.DISABLED_ON_COMMAND_LINE
            continue

        log.debug(f"trying to import porcupine.plugins.{info.name}")
        start = time.time()

        try:
            info.module = importlib.import_module(f'porcupine.plugins.{info.name}')
            info.setup_before = set(getattr(info.module, 'setup_before', []))
            info.setup_after = set(getattr(info.module, 'setup_after', []))
        except Exception:
            log.exception(f"can't import porcupine.plugins.{info.name}")
            info.status = Status.IMPORT_FAILED
            info.error = traceback.format_exc()
            continue

        duration = time.time() - start
        log.debug("imported porcupine.plugins.%s in %.3f milliseconds", info.name, duration*1000)


def _get_successfully_imported_infos() -> List[PluginInfo]:
    # If all plugins are disabled, then import_plugins() doesn't run at all and plugin_infos is empty
    return [
        info for info in plugin_infos
        if info.status == Status.LOADING
    ]


# undocumented on purpose, don't use in plugins
# TODO: document what setup_argument_parser() function in a plugin does
def run_setup_argument_parser_functions(parser: argparse.ArgumentParser) -> None:
    for info in _get_successfully_imported_infos():
        assert info.module is not None
        if hasattr(info.module, 'setup_argument_parser'):
            try:
                info.module.setup_argument_parser(parser)
            except Exception:
                log.exception(f"{info.name}.setup_argument_parser() doesn't work")
                info.status = Status.SETUP_FAILED
                info.error = traceback.format_exc()
            else:
                info.status = Status.ACTIVE


# undocumented on purpose, don't use in plugins
def run_setup_functions(shuffle: bool) -> None:
    imported_infos = _get_successfully_imported_infos()

    # setup_before and setup_after may contain names of plugins that are not
    # installed because they are for controlling the loading order. That's fine
    # because toposort ignores missing things.
    dependencies: Dict[str, Set[str]] = {}
    for info in imported_infos:
        dependencies.setdefault(info.name, set()).update(info.setup_after)
        for reverse_dependency in info.setup_before:
            dependencies.setdefault(reverse_dependency, set()).add(info.name)

    # the toposort will partially work even if there's a circular
    # dependency, the CircularDependencyError is raised after doing
    # everything possible (see source code)
    loading_order: List[str] = []
    try:
        # https://github.com/python/mypy/issues/9253
        make_list: Callable[[Iterable[str]], List[str]] = list
        for names in map(make_list, toposort.toposort(dependencies)):
            if shuffle:
                # for plugin developers wanting to make sure that the
                # dependencies specified in setup_before and setup_after
                # are correct
                random.shuffle(names)
            else:
                # for consistency in UI (e.g. always same order of menu items)
                names.sort()
            loading_order.extend(names)
        loadable_infos = imported_infos

    except toposort.CircularDependencyError as e:
        log.exception("circular dependency")

        for info in imported_infos:
            if info.name in loading_order:
                loadable_infos.append(info)
            else:
                info.status = Status.CIRCULAR_DEPENDENCY_ERROR
                parts = ', '.join(f"{a} depends on {b}" for a, b in e.data.items())
                info.error = f"Circular dependency error: {parts}"

    loadable_infos.sort(key=(lambda info: loading_order.index(info.name)))
    for info in loadable_infos:
        start = time.time()
        try:
            assert info.module is not None
            info.module.setup()
        except Exception:
            log.exception(f"{info.name}.setup() doesn't work")
            info.status = Status.SETUP_FAILED
            info.error = traceback.format_exc()
        else:
            info.status = Status.ACTIVE

        duration = time.time() - start
        log.debug("ran %s.setup() in %.3f milliseconds", info.name, duration*1000)
