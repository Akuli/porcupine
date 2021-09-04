# note about virtual events: sometimes running any_widget.update()
# before generating a virtual event is needed for the virtual event to
# actually do something, if you have weird problems with tests try
# adding any_widget.update() calls
# see also update(3tcl)

import logging
import operator
import os
import subprocess
import sys
import tempfile
import tkinter

import appdirs
import pytest

import porcupine
from porcupine import dirs, get_main_window, get_paned_window, get_tab_manager, plugins, tabs, utils
from porcupine.__main__ import main
from porcupine.plugins.directory_tree import DirectoryTree


# https://docs.pytest.org/en/latest/example/simple.html#dynamically-adding-command-line-options
#
# use 'pytest --test-pastebins' to run tests that send stuff to pastebins, it's
# disabled by default because pastebins might block you for using them
# repeatedly too fast
def pytest_addoption(parser):
    parser.addoption(
        "--test-pastebins",
        action="store_true",
        default=False,
        help="run tests that invoke online pastebins",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--test-pastebins"):
        # --test-pastebins given in cli: do not skip pastebin tests
        return
    skip_pastebins = pytest.mark.skip(reason="need --test-pastebins to run")
    for item in items:
        if "pastebin_test" in item.keywords:
            item.add_marker(skip_pastebins)


class MonkeypatchedAppDirs(appdirs.AppDirs):
    user_cache_dir = property(operator.attrgetter("_cache"))
    user_config_dir = property(operator.attrgetter("_config"))
    user_log_dir = property(operator.attrgetter("_logs"))


@pytest.fixture(scope="session")
def monkeypatch_dirs():
    # avoid errors from user's custom plugins
    user_plugindir = plugins.__path__.pop(0)
    assert user_plugindir == os.path.join(dirs.user_config_dir, "plugins")

    with tempfile.TemporaryDirectory() as d:
        # This is a hack because:
        #   - pytest monkeypatch fixture doesn't work (not for scope='session')
        #   - assigning to dirs.user_cache_dir doesn't work (appdirs uses @property)
        #   - "porcupine.dirs = blahblah" doesn't work (from porcupine import dirs)
        dirs.__class__ = MonkeypatchedAppDirs
        dirs._cache = os.path.join(d, "cache")
        dirs._config = os.path.join(d, "config")
        dirs._logs = os.path.join(d, "logs")
        assert dirs.user_cache_dir.startswith(d)
        yield


@pytest.fixture(scope="session", autouse=True)
def porcusession(monkeypatch_dirs):
    # these errors should not occur while porcupine is running
    with pytest.raises(RuntimeError):
        get_main_window()

    with pytest.raises(RuntimeError):
        get_tab_manager()

    # monkeypatch fixture doesn't work for this for whatever reason
    # porcupine calls mainloop(), but we want it to return immediately for tests
    old_args = sys.argv[1:]
    old_mainloop = tkinter.Tk.mainloop
    try:
        # --verbose here doesn't work for whatever reason
        # I tried to make it work, but then pytest caplog fixture didn't work
        sys.argv[1:] = ["--shuffle-plugins"]
        tkinter.Tk.mainloop = lambda self: None
        main()
    finally:
        sys.argv[1:] = old_args
        tkinter.Tk.mainloop = old_mainloop

    yield

    # avoid "Do you want to save" dialogs
    for tab in list(porcupine.get_tab_manager().tabs()):
        porcupine.get_tab_manager().close_tab(tab)

    porcupine.quit()


@pytest.fixture
def tabmanager(porcusession):
    assert not get_tab_manager().tabs(), "something hasn't cleaned up its tabs"
    yield get_tab_manager()
    for tab in get_tab_manager().tabs():
        get_tab_manager().close_tab(tab)


@pytest.fixture
def filetab(porcusession, tabmanager):
    tab = tabs.FileTab(tabmanager)
    tabmanager.add_tab(tab)
    return tab


# TODO: consider longer name
@pytest.fixture
def tree():
    [tree] = [
        w
        for w in utils.get_children_recursively(get_paned_window())
        if isinstance(w, DirectoryTree)
    ]
    for child in tree.get_children(""):
        tree.delete(child)
    yield tree


@pytest.fixture(scope="function", autouse=True)
def check_nothing_logged(request):
    if "caplog" in request.fixturenames:
        # Test uses caplog fixture, expects to get logging errors
        yield
    else:
        # Fail test if it logs an error
        def emit(record: logging.LogRecord):
            raise RuntimeError(f"test logged error: {record}")

        handler = logging.Handler()
        handler.setLevel(logging.ERROR)
        handler.emit = emit
        logging.getLogger().addHandler(handler)
        yield
        logging.getLogger().removeHandler(handler)


@pytest.fixture
def run_porcupine():
    def actually_run_porcupine(args, expected_exit_status):
        run_result = subprocess.run(
            [sys.executable, "-m", "porcupine"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )
        assert run_result.returncode == expected_exit_status
        return run_result.stdout

    return actually_run_porcupine
