"""Loads plugins from `porcupine.plugins`.

This file contains a lot of try/except, so that one bad plugin is unlikely to
crash the whole editor.

See dev-doc/architecture-and-design.md for an introduction to plugins.

This file generates a `<<PluginsLoaded>>` virtual event on the main window when
when the `setup()` methods of all plugins have been called on startup. Bind to
it if you want to run things that must not happen until plugins are ready
for it.

Note that `<<PluginsLoaded>>` also runs after successfully setting up a plugin
while Porcupine is running.
"""
from __future__ import annotations

import argparse
import dataclasses
import enum
import importlib.machinery
import logging
import pkgutil
import random
import time
import traceback
from collections.abc import Iterator, Sequence
from typing import Any, Callable, TypeVar, cast

from porcupine import get_main_window
from porcupine.plugins import __path__ as plugin_paths
from porcupine.settings import global_settings

log = logging.getLogger(__name__)


class Status(enum.Enum):
    """This represents the status of a plugin in the Porcupine process."""

    # The plugin hasn't been set up successfully yet, but no errors
    # preventing the setup have occurred.
    LOADING = enum.auto()

    # The plugin was imported and its `setup()` function was called successfully.
    ACTIVE = enum.auto()

    # The plugin wasn't loaded because it's in the `disabled_plugins` setting.
    # See `porcupine.settings`.
    DISABLED_BY_SETTINGS = enum.auto()

    # The plugin wasn't loaded because it was listed in a `--without-plugins`
    # argument given to Porcupine.
    DISABLED_ON_COMMAND_LINE = enum.auto()

    # Importing the plugin raised an error.
    IMPORT_FAILED = enum.auto()

    # The plugin was imported successfully, but its `setup()` function
    # raised an exception or logged an error.
    #
    # In a plugin named `foo`, any message logged with severity `ERROR`
    # or `CRITICAL` to the logger named `porcupine.plugins.foo` counts as
    # logging an error. Therefore you can do this:
    #
    #    import logging
    #
    #    log = logging.getLogger(__name__)  # __name__ == "porcupine.plugins.foo"
    #
    #    def setup() -> None:
    #        if bar_is_installed:
    #            ...
    #        else:
    #            log.error("bar is not installed")
    #
    # When bar is not installed, this plugin will show a one-line error
    # message in the plugin manager and the terminal. If an exception is
    # raised, the full traceback is shown instead.
    SETUP_FAILED = enum.auto()

    # Plugins with this status were imported, but their `setup_before` and
    # `setup_after` lists make it impossible to determine the correct order
    # for calling their `setup()` function.
    #
    # For example, if plugin A should be set up before B, B should be
    # set up before C, and C should be set up before A, then A, B
    # and C will all fail to load with this status.
    CIRCULAR_DEPENDENCY_ERROR = enum.auto()


@dataclasses.dataclass(eq=False)
class PluginInfo:
    """
    This dataclass represents a plugin.

    The value of `error` depends on `status`:
    - `LOADING`: `error` is `None`
    - `ACTIVE`: `error` is `None`
    - `DISABLED_BY_SETTINGS`: `error` is `None`
    - `DISABLED_ON_COMMAND_LINE`: `error` is `None`
    - `IMPORT_FAILED`: `error` is a Python error message
    - `SETUP_FAILED`: `error` is a Python error message
    - `CIRCULAR_DEPENDENCY_ERROR`: `error` is a user-readable one-line message
    """

    name: str  # name "foo" means this is porcupine/plugins/foo.py
    came_with_porcupine: bool
    status: Status
    module: Any | None  # you have to check for None, otherwise mypy won't complain
    error: str | None


# Includes all plugins, including disabled plugins and plugins that failed to load.
_mutable_plugin_infos: list[PluginInfo] = []

_dependencies: dict[PluginInfo, set[PluginInfo]] = {}

plugin_infos: Sequence[PluginInfo] = _mutable_plugin_infos  # don't modify outside this file


def _run_setup_argument_parser_function(info: PluginInfo, parser: argparse.ArgumentParser) -> None:
    assert info.status == Status.LOADING
    assert info.module is not None

    if hasattr(info.module, "setup_argument_parser"):
        start = time.perf_counter()
        try:
            info.module.setup_argument_parser(parser)
        except Exception:
            log.exception(f"{info.name}.setup_argument_parser() doesn't work")
            info.status = Status.SETUP_FAILED
            info.error = traceback.format_exc()

        duration = time.perf_counter() - start
        log.debug("ran %s.setup_argument_parser() in %.3f milliseconds", info.name, duration * 1000)


def _import_plugin(info: PluginInfo) -> None:
    assert info.status == Status.LOADING
    assert info.module is None

    log.debug(f"trying to import porcupine.plugins.{info.name}")
    start = time.perf_counter()

    try:
        info.module = importlib.import_module(f"porcupine.plugins.{info.name}")
        setup_before = set(getattr(info.module, "setup_before", []))
        setup_after = set(getattr(info.module, "setup_after", []))
    except Exception:
        log.exception(f"can't import porcupine.plugins.{info.name}")
        info.status = Status.IMPORT_FAILED
        info.error = traceback.format_exc()
        return

    for dep_info in plugin_infos:
        if dep_info.name in setup_after:
            _dependencies[info].add(dep_info)
        if dep_info.name in setup_before:
            _dependencies[dep_info].add(info)

    duration = time.perf_counter() - start
    log.debug("imported porcupine.plugins.%s in %.3f milliseconds", info.name, duration * 1000)


# Remember to generate <<PluginsLoaded>> when this succeeds
def _run_setup_and_set_status(info: PluginInfo) -> None:
    assert info.status == Status.LOADING
    assert info.module is not None

    error_log: list[logging.LogRecord] = []
    logger = logging.getLogger(f"porcupine.plugins.{info.name}")
    handler = logging.Handler()
    handler.setLevel(logging.ERROR)
    handler.emit = error_log.append  # type: ignore
    logger.addHandler(handler)

    if hasattr(info.module, "setup"):
        start = time.perf_counter()
        try:
            log.debug(f"calling porcupine.plugins.{info.name}.setup()")
            info.module.setup()
        except Exception:
            log.exception(f"{info.name}.setup() doesn't work")
            info.status = Status.SETUP_FAILED
            info.error = traceback.format_exc()
        else:
            if error_log:
                info.status = Status.SETUP_FAILED
                info.error = "".join(
                    f"{record.levelname}: {record.message}\n" for record in error_log
                )
            else:
                if not getattr(info.module, "__doc__", None):
                    log.warning(
                        f"Please add a docstring to the {info.name!r} plugin. It will show up in"
                        f" the plugin manager when the {info.name!r} plugin is selected, so that"
                        " users know what the plugin does."
                    )
                info.status = Status.ACTIVE

        duration = time.perf_counter() - start
        logger.debug("ran %s.setup() in %.3f milliseconds", info.name, duration * 1000)
    else:
        info.status = Status.SETUP_FAILED
        info.error = (
            "There is no setup() function. Make sure to include a setup function in your plugin."
        )
        log.warning(f"Calling {info.name!r} plugin's setup() function failed.\n{info.error}")

    logger.removeHandler(handler)


def _did_plugin_come_with_porcupine(finder: object) -> bool:
    return isinstance(finder, importlib.machinery.FileFinder) and finder.path == plugin_paths[-1]


# undocumented on purpose, don't use in plugins
def import_plugins(disabled_on_command_line: list[str]) -> None:
    assert not _mutable_plugin_infos and not _dependencies
    _mutable_plugin_infos.extend(
        PluginInfo(
            name=name,
            came_with_porcupine=_did_plugin_come_with_porcupine(finder),
            status=Status.LOADING,
            module=None,
            error=None,
        )
        for finder, name, is_pkg in pkgutil.iter_modules(plugin_paths)
        if not name.startswith("_")
    )
    _dependencies.update({info: set() for info in plugin_infos})

    for info in _mutable_plugin_infos:
        # If it's disabled in settings and on command line, then status is set
        # to DISABLED_BY_SETTINGS. This makes more sense for the user of the
        # plugin manager dialog.
        if info.name in global_settings.get("disabled_plugins", list[str]):
            info.status = Status.DISABLED_BY_SETTINGS
            continue
        if info.name in disabled_on_command_line:
            info.status = Status.DISABLED_ON_COMMAND_LINE
            continue
        _import_plugin(info)


# undocumented on purpose, don't use in plugins
# TODO: document what setup_argument_parser() function in a plugin does
def run_setup_argument_parser_functions(parser: argparse.ArgumentParser) -> None:
    for info in plugin_infos:
        if info.status == Status.LOADING:
            _run_setup_argument_parser_function(info, parser)


def _handle_circular_dependency(cycle: Sequence[PluginInfo]) -> None:
    error_message = " -> ".join(info.name for info in cycle)
    log.error(f"circular dependency: {error_message}")
    for info in cycle:
        info.status = Status.CIRCULAR_DEPENDENCY_ERROR
        info.error = f"Circular dependency error: {error_message}"


_T = TypeVar("_T")


# This is generic to make it easier to test. Tests use ints instead of plugin infos.
def _decide_loading_order(
    dependencies: dict[_T, set[_T]], cycle_handler: Callable[[Sequence[_T]], None]
) -> Iterator[set[_T]]:
    dependencies = {item: deps.copy() for item, deps in dependencies.items()}

    # Create a set of all plugins.
    remaining = set(dependencies.keys())
    for deps in dependencies.values():
        remaining.update(deps)

    while remaining:
        # Find plugins with no dependencies. We can set them up now.
        satisfied = {item for item in remaining if not dependencies.get(item)}

        if satisfied:
            # We have found plugins that can be set up now. Their dependencies are
            # ready, and we can set them up in any order relative to each other.
            yield satisfied
            forget_about = satisfied
        else:
            # All remaining plugins have at least one dependency.
            # This means that we must have cycles. Let's find one such cycle.
            cycle = [next(iter(remaining))]
            while cycle.count(cycle[-1]) == 1:
                cycle.append(next(iter(dependencies[cycle[-1]])))

            # Throw away the non-cyclic start.
            # For example, 1->2->3->4->5->3 becomes 3->4->5->3.
            del cycle[: cycle.index(cycle[-1])]

            cycle_handler(cycle)
            forget_about = set(cycle)

        remaining.difference_update(forget_about)
        for deps in dependencies.values():
            deps.difference_update(forget_about)


# undocumented on purpose, don't use in plugins
def run_setup_functions(shuffle: bool) -> None:
    """Called during Porcupine startup. Do not call from plugins."""
    loading_order = []
    for infos in _decide_loading_order(_dependencies, _handle_circular_dependency):
        load_list = [info for info in infos if info.status == Status.LOADING]
        if shuffle:
            # for plugin developers wanting to make sure that the
            # dependencies specified in setup_before and setup_after
            # are correct
            random.shuffle(load_list)
        else:
            # for consistency in UI (e.g. always same order of menu items)
            load_list.sort(key=(lambda info: info.name))
        loading_order.extend(load_list)

    for info in loading_order:
        assert info.status == Status.LOADING
        _run_setup_and_set_status(info)

    get_main_window().event_generate("<<PluginsLoaded>>")


def can_setup_while_running(info: PluginInfo) -> bool:
    """
    Returns whether the plugin can be set up now, without having to
    restart Porcupine.
    """
    if info.status not in {Status.DISABLED_BY_SETTINGS, Status.DISABLED_ON_COMMAND_LINE}:
        return False

    if info.module is None:
        # Importing may give more information about dependencies, needed below
        old_status = info.status
        info.status = Status.LOADING
        _import_plugin(info)
        if info.status != Status.LOADING:  # error
            return False
        info.status = old_status

    # If a plugin defines setup_argument_parser, it likely wants it to run on
    # startup, and now it's too late.
    if hasattr(info.module, "setup_argument_parser"):
        return False

    # Check whether no other active plugin depends on loading after this plugin
    setup_preventors = [
        other.name
        for other, other_must_setup_after_these in _dependencies.items()
        if other.status == Status.ACTIVE and info in other_must_setup_after_these
    ]
    if setup_preventors:
        log.info(
            f"can't setup {info.name} now because it must be done before setting up the following"
            " plugins, which are already active: " + "\n".join(setup_preventors)
        )
        return False

    return True


def setup_while_running(info: PluginInfo) -> None:
    """Run the `setup_argument_parser()` and `setup()` functions now.

    Before calling this function, make sure that the
    `can_setup_while_running()` function returns `True`.
    """
    info.status = Status.LOADING

    dummy_parser = argparse.ArgumentParser()
    _run_setup_argument_parser_function(info, dummy_parser)

    # Cast is needed to confuse mypy. It thinks that _run_setup_and_set_status()
    # won't change info.status, but as the function name strongly suggests, it will.
    #
    # See also: https://github.com/python/mypy/issues/12598
    if cast(object, info.status) != Status.LOADING:
        # loading plugin failed with error
        return

    _run_setup_and_set_status(info)
    assert info.status != Status.LOADING
    if info.status == Status.ACTIVE:
        get_main_window().event_generate("<<PluginsLoaded>>")
