# TODO: create much more tests for langserver
import time
import tkinter

from sansio_lsp_client import ClientState

from porcupine import get_main_window
from porcupine.plugins.langserver import langservers


def wait_until(condition):
    end = time.time() + 10  # big timeout because windows is slow
    while time.time() < end:
        get_main_window().update()
        if condition():
            return
    raise RuntimeError("timed out waiting")


def wait_for_langserver_to_start(filetab):
    wait_until(
        lambda: any(
            filetab in ls.tabs_opened and ls._lsp_client.state == ClientState.NORMAL
            for ls in langservers.values()
        )
    )


def test_basic(filetab, tmp_path):
    filetab.textwidget.insert(
        "1.0",
        """\
def foo():
    print("Lul")

foo()
""",
    )
    filetab.save_as(tmp_path / "foo.py")  # starts lang server
    wait_for_langserver_to_start(filetab)

    # Put cursor to middle of calling foo()
    filetab.textwidget.mark_set("insert", "end - 1 char")
    filetab.textwidget.mark_set("insert", "insert - 1 line")
    filetab.textwidget.mark_set("insert", "insert + 2 chars")

    filetab.textwidget.event_generate("<<JumpToDefinition>>")
    wait_until(lambda: bool(filetab.textwidget.tag_ranges("sel")))

    assert filetab.textwidget.get("sel.first", "sel.last") == "foo"
    assert filetab.textwidget.get("sel.first linestart", "sel.last lineend") == "def foo():"


def test_two_definitions(filetab, tmp_path, mocker):
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
    wait_for_langserver_to_start(filetab)

    # Put cursor to middle of calling foo()
    filetab.textwidget.mark_set("insert", "end - 1 char")
    filetab.textwidget.mark_set("insert", "insert - 1 line")
    filetab.textwidget.mark_set("insert", "insert + 2 chars")

    mocker.patch("tkinter.Menu")
    filetab.textwidget.event_generate("<<JumpToDefinition>>")
    wait_until(lambda: tkinter.Menu.call_args is not None)

    # It should add two menu items pointing at 2 different lines
    [first_call, second_call] = tkinter.Menu.return_value.add_command.call_args_list
    assert "Line 2" in str(first_call)
    assert "Line 5" in str(second_call)

    # Click first menu item, [1] means kwargs
    first_call[1]["command"]()
    assert filetab.textwidget.get("sel.first", "sel.last") == "foo"
    assert (
        filetab.textwidget.get("sel.first linestart", "sel.last lineend")
        == "    def foo():  # first"
    )
