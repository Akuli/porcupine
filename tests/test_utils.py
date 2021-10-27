import dataclasses
import shutil
import subprocess
import sys
import typing
from pathlib import Path

import pytest

from porcupine import get_main_window, utils


def test_bind_with_data_string():
    # i don't know why the main window works better with this than a
    # temporary tkinter.Frame()
    events = []
    utils.bind_with_data(get_main_window(), "<<Asd>>", events.append, add=True)
    get_main_window().event_generate("<<Asd>>", data="hello")

    [event] = events
    assert event.widget is get_main_window()
    assert event.data_string == "hello"


@dataclasses.dataclass
class Foo:
    message: str
    num: int


@dataclasses.dataclass
class Bar(utils.EventDataclass):
    foos: typing.List[Foo]


def test_bind_with_data_class():
    events = []
    utils.bind_with_data(get_main_window(), "<<DataclassAsd>>", events.append, add=True)
    get_main_window().event_generate(
        "<<DataclassAsd>>", data=Bar(foos=[Foo(message="abc", num=123)])
    )

    [event] = events
    bar = event.data_class(Bar)
    [foo] = bar.foos
    assert foo.message == "abc"
    assert foo.num == 123


if sys.platform == "darwin":
    binding_test_cases = [
        ("<<Menubar:Edit/Anchors/Add or remove on this line>>", "⇧⌥A", "Shift-Alt-A"),
        ("<<Menubar:Edit/Anchors/Jump to next>>", "⇧⌥Down", "Shift-Alt-Down"),  # sucks but unused
        ("<<Menubar:Edit/Fold>>", "⌥F", "Alt-F"),
        ("<<Menubar:File/New File>>", "⌘N", "Command-N"),
        ("<<Menubar:File/Save As>>", "⇧⌘S", "Shift-Command-S"),
        ("<<Menubar:File/Save>>", "⌘S", "Command-S"),
        ("<<Menubar:View/Bigger Font>>", "⌘+", "Command-+"),
        ("<<Menubar:View/Reset Font Size>>", "⌘0", "Command-0"),
        ("<<Menubar:View/Smaller Font>>", "⌘-", "Command--"),
        ("<<Menubar:Edit/Jump to definition>>", "⌘⏎", "Command-Return"),
        (
            "<<Menubar:Edit/Jump to definition>>",
            "⌘-click",
            "Command-click",
        ),  # not possible to show in menu
        ("<<UtilsTestEvent>>", "⇧⌥-click", ""),  # not possible to show in menu
    ]
else:
    # menu option doesn't matter
    binding_test_cases = [
        ("<<Menubar:Edit/Anchors/Add or remove on this line>>", "Alt+Shift+A", "Alt+Shift+A"),
        ("<<Menubar:Edit/Anchors/Jump to next>>", "Alt+Shift+Down", "Alt+Shift+Down"),
        ("<<Menubar:Edit/Fold>>", "Alt+F", "Alt+F"),
        ("<<Menubar:File/New File>>", "Ctrl+N", "Ctrl+N"),
        ("<<Menubar:File/Save As>>", "Ctrl+Shift+S", "Ctrl+Shift+S"),
        ("<<Menubar:File/Save>>", "Ctrl+S", "Ctrl+S"),
        ("<<Menubar:View/Bigger Font>>", "Ctrl+Plus", "Ctrl+Plus"),
        ("<<Menubar:View/Reset Font Size>>", "Ctrl+Zero", "Ctrl+Zero"),
        ("<<Menubar:View/Smaller Font>>", "Ctrl+Minus", "Ctrl+Minus"),
        ("<<Menubar:Edit/Jump to definition>>", "Ctrl-Return", "Ctrl-Return"),
        (
            "<<Menubar:Edit/Jump to definition>>",
            "Ctrl-click",
            "Ctrl-click",
        ),  # not possible to show in menu
        ("<<UtilsTestEvent>>", "Alt+Shift+click", "Alt+Shift+click"),
    ]


@pytest.mark.parametrize("binding, menu_false_text, menu_true_text", binding_test_cases)
def test_get_binding(binding, menu_false_text, menu_true_text):
    # User-wide keybindings.tcl is not loaded when tests run

    # Old test case, currently unused
    get_main_window().tk.eval("event add <<UtilsTestEvent>> <Alt-Shift-Button-1>")

    false_text = utils.get_binding(binding, menu=False, many=True)
    true_text = utils.get_binding(binding, menu=True, many=True)
    assert menu_false_text in false_text
    assert menu_true_text in true_text


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_project_root(tmp_path):
    (tmp_path / "foo").mkdir()
    (tmp_path / "bar.py").touch()
    (tmp_path / "foo" / "baz.py").touch()
    (tmp_path / "foo" / "README.md").touch()
    (tmp_path / "README.md").touch()

    assert utils.find_project_root(tmp_path / "bar.py") == tmp_path
    assert utils.find_project_root(tmp_path / "foo" / "baz.py") == tmp_path / "foo"
    subprocess.run("git init -q", cwd=tmp_path, shell=True, check=True)
    assert utils.find_project_root(tmp_path / "foo" / "baz.py") == tmp_path


def test_format_command():
    assert utils.format_command("{foo} --help", {"foo": "bar baz"}) == ["bar baz", "--help"]

    if sys.platform == "win32":
        # https://github.com/Akuli/porcupine/issues/154#issuecomment-849102842
        path = r"C:\Users\Martin\tetris\env\Scripts\python.exe"
        assert utils.format_command(path + " {file}", {"file": "tetris.py"}) == [path, "tetris.py"]
    else:
        assert utils.format_command(r"foo\ bar", {}) == ["foo bar"]


def test_file_url_to_path():
    if sys.platform == "win32":
        paths = [Path(r"\\Server\Share\Test\Foo Bar.txt"), Path(r"C:\Users\Akuli\Foo Bar.txt")]
    else:
        paths = [Path("/home/akuli/Foo Bar.txt")]

    for path in paths:
        assert utils.file_url_to_path(path.as_uri()) == path
