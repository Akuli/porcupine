import dataclasses
import shutil
import subprocess
import sys
import typing
from pathlib import Path
from tkinter import ttk

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


def test_get_children_recursively():
    parent = ttk.Frame()
    try:
        child1 = ttk.Button(parent)
        child2 = ttk.Frame(parent)
        child2a = ttk.Progressbar(child2)
        child2b = ttk.Sizegrip(child2)

        assert list(utils.get_children_recursively(parent)) == [child1, child2, child2a, child2b]
        assert list(utils.get_children_recursively(parent, include_parent=True)) == [
            parent,
            child1,
            child2,
            child2a,
            child2b,
        ]
    finally:
        parent.destroy()


def test_get_binding():
    # Old test case, currently unused
    get_main_window().tk.eval("event add <<UtilsTestEvent>> <Alt-Shift-Button-1>")

    # User-wide keybindings.tcl is not loaded when tests run
    if sys.platform == "darwin":
        # Tk will show these with the proper symbols and stuff when these go to menu
        assert utils.get_binding("<<Menubar:File/New File>>", menu=True) == "Command-N"
        assert utils.get_binding("<<Menubar:File/Save>>", menu=True) == "Command-S"
        assert utils.get_binding("<<Menubar:File/Save As>>", menu=True) == "Command-Shift-S"
        assert utils.get_binding("<<Menubar:View/Bigger Font>>", menu=True) == "Command-+"
        assert utils.get_binding("<<Menubar:View/Smaller Font>>", menu=True) == "Command--"
        assert utils.get_binding("<<Menubar:View/Reset Font Size>>", menu=True) == "Command-0"
        assert utils.get_binding("<<Menubar:Edit/Fold>>", menu=True) == "Alt-F"
        assert utils.get_binding("<<Menubar:Run/Run>>", menu=True) == "F5"
        assert utils.get_binding("<<Urls:OpenWithMouse>>", menu=True) == ""  # not possible to show
        assert utils.get_binding("<<Urls:OpenWithKeyboard>>", menu=True) == "Shift-Alt-Return"
        assert utils.get_binding("<<UtilsTestEvent>>", menu=True) == ""  # not possible to show

        assert utils.get_binding("<<Menubar:File/New File>>", menu=False) == "⌘N"
        assert utils.get_binding("<<Menubar:File/Save>>", menu=False) == "⌘S"
        assert utils.get_binding("<<Menubar:File/Save As>>", menu=False) == "⇧⌘S"
        assert utils.get_binding("<<Menubar:View/Bigger Font>>", menu=False) == "⌘+"
        assert utils.get_binding("<<Menubar:View/Smaller Font>>", menu=False) == "⌘-"
        assert utils.get_binding("<<Menubar:View/Reset Font Size>>", menu=False) == "⌘0"
        assert utils.get_binding("<<Menubar:Edit/Fold>>", menu=False) == "⌥F"
        assert utils.get_binding("<<Menubar:Run/Run>>", menu=False) == "F5"
        assert utils.get_binding("<<Urls:OpenWithMouse>>", menu=False) == "double-click"
        assert utils.get_binding("<<Urls:OpenWithKeyboard>>", menu=False) == "⇧⌥⏎"
        assert utils.get_binding("<<UtilsTestEvent>>", menu=False) == "⇧⌥-click"

    else:
        # menu option has no effect
        for boolean in [True, False]:
            assert utils.get_binding("<<Menubar:File/New File>>", menu=boolean) == "Ctrl+N"
            assert utils.get_binding("<<Menubar:File/Save>>", menu=boolean) == "Ctrl+S"
            assert utils.get_binding("<<Menubar:File/Save As>>", menu=boolean) == "Ctrl+Shift+S"
            assert utils.get_binding("<<Menubar:View/Bigger Font>>", menu=boolean) == "Ctrl+Plus"
            assert utils.get_binding("<<Menubar:View/Smaller Font>>", menu=boolean) == "Ctrl+Minus"
            assert (
                utils.get_binding("<<Menubar:View/Reset Font Size>>", menu=boolean) == "Ctrl+Zero"
            )
            assert utils.get_binding("<<Menubar:Edit/Fold>>", menu=boolean) == "Alt+F"
            assert utils.get_binding("<<Menubar:Run/Run>>", menu=boolean) == "F5"
            assert utils.get_binding("<<Urls:OpenWithMouse>>", menu=boolean) == "double-click"
            assert utils.get_binding("<<Urls:OpenWithKeyboard>>", menu=boolean) == "Shift+Alt+Enter"
            assert utils.get_binding("<<UtilsTestEvent>>", menu=boolean) == "Shift+Alt+click"


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


def test_format_command(monkeypatch):
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
