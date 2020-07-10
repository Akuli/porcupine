# note about virtual events: sometimes running any_widget.update()
# before generating a virtual event is needed for the virtual event to
# actually do something, if you have weird problems with tests try
# adding any_widget.update() calls
# see also update(3tcl)

import atexit
import pathlib
import shutil
import tempfile
import tkinter

import pytest

import porcupine
from porcupine import (dirs, get_main_window, get_tab_manager, tabs,
                       pluginloader)
from porcupine import filetypes as filetypes_module

# TODO: something else will be needed when testing the filetypes
tempdir = tempfile.mkdtemp()
dirs.configdir = pathlib.Path(tempdir)
atexit.register(shutil.rmtree, str(tempdir))
del tempdir


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


@pytest.fixture(scope='session')
def porcusession():
    # these errors should not occur after the init
    with pytest.raises(RuntimeError):
        get_main_window()

    with pytest.raises(RuntimeError):
        get_tab_manager()

    root = tkinter.Tk()
    root.withdraw()
    porcupine.init(root)

    plugin_names = pluginloader.find_plugins()
    plugin_names.remove('restart')   # this plugins opens tabs
    #plugin_names = []
    pluginloader.load(plugin_names, shuffle=True)

    yield
    porcupine.quit()
    root.destroy()


# TODO: can this be deleted safely?
@pytest.fixture(scope='session')
def filetypes(porcusession):
    return filetypes_module


@pytest.fixture
def tabmanager(porcusession):
    assert not get_tab_manager().tabs(), "something hasn't cleaned up its tabs"
    yield get_tab_manager()
    assert not get_tab_manager().tabs(), "the test didn't clean up its tabs"


@pytest.fixture
def filetab(porcusession, tabmanager):
    tab = tabs.FileTab(tabmanager)
    tabmanager.add_tab(tab)
    yield tab
    tabmanager.close_tab(tab)
