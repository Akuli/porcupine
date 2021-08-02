import sys

import pytest


if sys.platform == "darwin":
    contmand_shift_backspace = "<Command-Shift-BackSpace>"
else:
    contmand_shift_backspace = "<Control-Shift-BackSpace>"


@pytest.mark.parametrize("event_string", ["<BackSpace>", contmand_shift_backspace])
def test_backspace_in_beginning_of_file(filetab, event_string):
    filetab.textwidget.insert("end", "a")
    filetab.textwidget.mark_set("insert", "1.0")
    filetab.textwidget.event_generate(event_string)
    assert filetab.textwidget.get("1.0", "end - 1 char") == "a"

    filetab.textwidget.tag_add("sel", "1.0", "1.1")
    filetab.textwidget.event_generate(event_string)
    assert filetab.textwidget.get("1.0", "end - 1 char") == ""
