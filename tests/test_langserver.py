# TODO: create much more tests

import time

from sansio_lsp_client import ClientState

from porcupine import get_main_window
from porcupine.plugins.langserver import langservers


def wait_until(condition):
    end = time.time() + 5
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


def test_jump_to_definition(filetab, tmp_path):
    filetab.textwidget.insert(
        "1.0",
        """\
def foo():
    print("Lul")

def bar():
    foo()
""",
    )
    filetab.save_as(tmp_path / "foo.py")  # starts lang server
    wait_for_langserver_to_start(filetab)

    filetab.textwidget.mark_set("insert", "5.5")  # in middle of calling foo()
    filetab.textwidget.event_generate("<<JumpToDefinition>>")
    wait_until(lambda: bool(filetab.textwidget.tag_ranges("sel")))

    assert filetab.textwidget.get("sel.first", "sel.last") == "foo"
    assert filetab.textwidget.get("sel.first linestart", "sel.last lineend") == "def foo():"
