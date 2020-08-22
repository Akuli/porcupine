# note about virtual events: sometimes running any_widget.update()
# before generating a virtual event is needed for the virtual event to
# actually do something, if you have weird problems with tests try
# adding any_widget.update() calls
# see also update(3tcl)

import pathlib
import sys
import tempfile
import tkinter

import pytest

import porcupine
from porcupine import dirs, get_main_window, get_tab_manager, plugins, tabs
from porcupine.__main__ import main


# this url is split on 2 lines because pep8, concatenate the lines when
# copy/pasting it to your browser:
#
#    https://docs.pytest.org/en/latest/example/simple.html#dynamically-adding-c
#    ommand-line-options
#
# use 'pytest --test-pastebins' to run tests that send stuff to pastebins, it's
# disabled by default because pastebins might block you for using them
# repeatedly too fast
def pytest_addoption(parser):
    parser.addoption(
        '--test-pastebins', action='store_true', default=False,
        help="run tests that invoke online pastebins")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--test-pastebins"):
        # --test-pastebins given in cli: do not skip pastebin tests
        return
    skip_pastebins = pytest.mark.skip(reason="need --test-pastebins to run")
    for item in items:
        if "pastebin_test" in item.keywords:
            item.add_marker(skip_pastebins)


# works with this:  from porcupine import dirs
# does NOT work:    from porcupine.dirs import configdir
@pytest.fixture(scope='session')
def monkeypatch_dirs():
    # avoid errors from user's custom plugins
    user_plugindir = plugins.__path__.pop(0)
    assert user_plugindir == str(dirs.configdir / 'plugins')

    with tempfile.TemporaryDirectory() as d:
        dirs.cachedir = pathlib.Path(d) / 'cache'
        dirs.configdir = pathlib.Path(d) / 'config'
        dirs.makedirs()
        yield


@pytest.fixture(scope='session')
def porcusession(monkeypatch_dirs):
    # these errors should not occur after the init
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
        sys.argv[1:] = ['--shuffle-plugins']
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
