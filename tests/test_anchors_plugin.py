import sys

import pytest

from porcupine.menubar import get_menu
from porcupine.settings import global_settings


def jump_5_times(filetab, how):
    assert sys.platform != "linux"
    locations = []
    for i in range(5):
        get_menu("Edit/Anchors").invoke(how)
        locations.append(filetab.textwidget.index("insert"))
    return locations


# TODO: set up windows in a VM and test this locally
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="cursor positions sometimes come out wrong on Windows"
)


def test_basic(filetab):
    filetab.textwidget.insert("end", "blah\n" * 10)

    # Set anchors on lines 2 and 5. Column numbers should get ignored.
    filetab.textwidget.mark_set("insert", "2.2")
    get_menu("Edit/Anchors").invoke("Add or remove on this line")
    filetab.textwidget.mark_set("insert", "5.3")
    get_menu("Edit/Anchors").invoke("Add or remove on this line")

    # Jump forwards, starting at the beginning of the file. Gets stuck at last anchor
    filetab.textwidget.mark_set("insert", "1.0")
    assert jump_5_times(filetab, "Jump to next") == ["2.0", "5.0", "5.0", "5.0", "5.0"]

    # Jump backwards
    filetab.textwidget.mark_set("insert", "end")
    assert jump_5_times(filetab, "Jump to previous") == ["5.0", "2.0", "2.0", "2.0", "2.0"]


@pytest.fixture
def cyclic_setting_enabled():
    global_settings.set("anchors_cycle", True)
    yield
    global_settings.reset("anchors_cycle")


def test_cyclic_jumping(filetab, cyclic_setting_enabled):
    filetab.textwidget.insert("end", "blah\n" * 10)

    # Set anchors on lines 2, 4 and 7
    filetab.textwidget.mark_set("insert", "2.0")
    get_menu("Edit/Anchors").invoke("Add or remove on this line")
    filetab.textwidget.mark_set("insert", "4.0")
    get_menu("Edit/Anchors").invoke("Add or remove on this line")
    filetab.textwidget.mark_set("insert", "7.0")
    get_menu("Edit/Anchors").invoke("Add or remove on this line")

    # Jump forwards and backwards. It cycles around now.
    filetab.textwidget.mark_set("insert", "1.0")
    assert jump_5_times(filetab, "Jump to next") == ["2.0", "4.0", "7.0", "2.0", "4.0"]
    assert jump_5_times(filetab, "Jump to previous") == ["2.0", "7.0", "4.0", "2.0", "7.0"]


# See #1353
def test_single_anchor_bug(filetab, cyclic_setting_enabled):
    filetab.textwidget.insert("end", "first row\nsecond row")

    # Line 1 does not have anchor, line 2 has it.
    filetab.textwidget.mark_set("insert", "2.0")
    get_menu("Edit/Anchors").invoke("Add or remove on this line")

    # Because cycling is enabled, jumping to previous anchor from line 1
    # will jump to the anchor below.
    filetab.textwidget.mark_set("insert", "1.0")
    get_menu("Edit/Anchors").invoke("Jump to previous")
    assert filetab.textwidget.index("insert") == "2.0"
