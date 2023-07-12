import sys

import pytest

from porcupine.menubar import get_menu
from porcupine.plugins.anchors import managers  # TODO: invoke the actions when they are a thing
from porcupine.settings import global_settings


def move_cursor(filetab, location):
    filetab.textwidget.mark_set("insert", location)
    if sys.platform == "win32":
        filetab.update()  # no idea why windows need this


def jump_5_times(filetab, which_way):
    locations = []
    for i in range(5):
        if which_way == "up":
            managers[filetab].jump_to_previous()
        elif which_way == "down":
            managers[filetab].jump_to_next()
        else:
            raise ValueError(which_way)
        locations.append(filetab.textwidget.index("insert"))

    return locations


def test_basic(filetab):
    filetab.textwidget.insert("end", "blah\n" * 10)

    # Set anchors on lines 2 and 5. Column numbers should get ignored.
    move_cursor(filetab, "2.2")
    managers[filetab].toggle()
    move_cursor(filetab, "5.3")
    managers[filetab].toggle()

    # Jump forwards, starting at the beginning of the file. Gets stuck at last anchor
    move_cursor(filetab, "1.0")
    assert jump_5_times(filetab, "down") == ["2.0", "5.0", "5.0", "5.0", "5.0"]

    # Jump backwards
    move_cursor(filetab, "end")
    assert jump_5_times(filetab, "up") == ["5.0", "2.0", "2.0", "2.0", "2.0"]


@pytest.fixture
def cyclic_setting_enabled():
    global_settings.set("anchors_cycle", True)
    yield
    global_settings.reset("anchors_cycle")


def test_cyclic_jumping(filetab, cyclic_setting_enabled):
    filetab.textwidget.insert("end", "blah\n" * 10)

    # Set anchors on lines 2, 4 and 7
    move_cursor(filetab, "2.0")
    managers[filetab].toggle()
    move_cursor(filetab, "4.0")
    managers[filetab].toggle()
    move_cursor(filetab, "7.0")
    managers[filetab].toggle()

    # Jump forwards and backwards. It cycles around now.
    move_cursor(filetab, "1.0")
    assert jump_5_times(filetab, "down") == ["2.0", "4.0", "7.0", "2.0", "4.0"]
    assert jump_5_times(filetab, "up") == ["2.0", "7.0", "4.0", "2.0", "7.0"]


def test_single_anchor_bug(filetab, cyclic_setting_enabled):
    # Setup is exactly as in #1353
    filetab.textwidget.insert("end", "first row\nsecond row")

    # Set an anchor point on row 1 & one anchor point on row 2.
    move_cursor(filetab, "1.0")
    managers[filetab].toggle()
    move_cursor(filetab, "2.0")
    managers[filetab].toggle()

    # Set cursor on row 1. Remove the anchor point on row 1.
    move_cursor(filetab, "1.0")
    managers[filetab].toggle()

    # Use keyboard shortcut to jump to next anchor (down).
    managers[filetab].jump_to_next()
    assert filetab.textwidget.index("insert") == "2.0"

    # Recreate anchor point on row 1. Make sure cursor is on row 1, then remove anchor point on row 1.
    move_cursor(filetab, "1.0")
    managers[filetab].toggle()
    managers[filetab].toggle()

    # Use keyboard shortcut to jump to previous anchor (up).
    managers[filetab].jump_to_previous()
    assert filetab.textwidget.index("insert") == "2.0"
