# TODO: create much more tests for langserver
import sys
import time

import pytest
if False:  # TODO: langservers are disabled :(
    from sansio_lsp_client import ClientState

from porcupine import get_main_window
from porcupine.plugins.langserver import langservers

pytestmark = pytest.mark.xfail(
    sys.version_info >= (3, 11),
    strict=True,
    reason="https://github.com/Akuli/porcupine/issues/1300",
)


def langserver_started(filetab):
    return lambda: any(
        filetab in ls.tabs_opened and ls._lsp_client.state == ClientState.NORMAL
        for ls in langservers.values()
    )


# Don't know why this is sometimes needed
def intense_super_update():
    start = time.time()
    while time.time() < start + 3:
        get_main_window().update()


@pytest.mark.xfail(strict=True, reason="langservers are disabled")
def test_basic(filetab, tmp_path, wait_until):
    filetab.textwidget.insert(
        "1.0",
        """\
def foo():
    print("Lul")

foo()
""",
    )
    filetab.save_as(tmp_path / "foo.py")  # starts lang server
    wait_until(langserver_started(filetab))

    # Put cursor to middle of calling foo()
    filetab.textwidget.mark_set("insert", "end - 1 char - 1 line + 2 chars")

    intense_super_update()
    filetab.textwidget.event_generate("<<JumpToDefinitionRequest>>")
    wait_until(lambda: bool(filetab.textwidget.tag_ranges("sel")))

    assert filetab.textwidget.get("sel.first", "sel.last") == "foo"
    assert filetab.textwidget.get("sel.first linestart", "sel.last lineend") == "def foo():"


@pytest.mark.xfail(strict=True, reason="langservers are disabled")
def test_two_definitions(filetab, tmp_path, mocker, wait_until):
    filetab.textwidget.insert(
        "1.0",
        """\
if lolwat:
    def foo():  # first
        print("Lul")
else:
    def foo():  # second
        print("Lul2")

foo()
""",
    )
    filetab.save_as(tmp_path / "foo.py")  # starts lang server
    wait_until(langserver_started(filetab))

    # Put cursor to middle of calling foo()
    filetab.textwidget.mark_set("insert", "end - 1 char")
    filetab.textwidget.mark_set("insert", "insert - 1 line")
    filetab.textwidget.mark_set("insert", "insert + 2 chars")

    mock = mocker.patch("tkinter.Menu")
    intense_super_update()
    filetab.textwidget.event_generate("<<JumpToDefinitionRequest>>")
    wait_until(lambda: mock.call_args is not None)

    # It should add two menu items pointing at 2 different lines
    [first_call, second_call] = mock.return_value.add_command.call_args_list
    assert "Line 2" in str(first_call)
    assert "Line 5" in str(second_call)

    # Click first menu item, [1] means kwargs
    first_call[1]["command"]()
    assert filetab.textwidget.get("sel.first", "sel.last") == "foo"
    assert (
        filetab.textwidget.get("sel.first linestart", "sel.last lineend")
        == "    def foo():  # first"
    )
