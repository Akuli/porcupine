import os
import shutil
import sys
import time
from typing import Any, List

import pytest

from porcupine import get_main_window, utils
from porcupine.plugins.run import no_terminal, settings, terminal


@pytest.fixture(autouse=True)
def isolated_history():
    assert not settings.get("run_history", List[Any])
    yield
    settings.set_("run_history", [])


@pytest.fixture
def fake_runner(tmp_path, monkeypatch):
    if sys.platform == "win32":
        path = tmp_path / "fake_runner.py"
        input_statement = "input()"
    else:
        path = tmp_path / "fake_runner.sh"
        input_statement = "read junk"

    shutil.copy(terminal.run_script, path)
    old_content = path.read_text()
    assert old_content.count(input_statement) == 1
    path.write_text(old_content.replace(input_statement, ""))

    monkeypatch.setattr("porcupine.plugins.run.terminal.run_script", path)


@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true", reason="no external terminal on github actions"
)
def test_external_terminal(filetab, tmp_path, monkeypatch, fake_runner):
    filetab.textwidget.insert("end", "open('file', 'w').write('hello')")
    filetab.save_as(tmp_path / "hello.py")
    get_main_window().event_generate("<<Menubar:Run/Repeat previous command>>")
    time.sleep(3)
    assert (tmp_path / "file").read_text() == "hello"


def tkinter_sleep(delay):
    end = time.time() + delay
    while time.time() < end:
        get_main_window().update()


def get_output_widget(filetab):
    return filetab.bottom_frame.nametowidget("run_output")


def get_output(filetab):
    return get_output_widget(filetab).get("1.0", "end - 1 char")


def test_output_in_porcupine_window(filetab, tmp_path):
    filetab.textwidget.insert("end", "print(12345)")
    filetab.save_as(tmp_path / "lol.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} lol.py", tmp_path)
    tkinter_sleep(3)

    assert "12345" in get_output(filetab)


def test_python_error_message(filetab, tabmanager, tmp_path):
    (tmp_path / "asdf.py").write_text("print(1)\nopen('this does not exist')\nprint(2)\n")
    filetab.textwidget.insert("end", "import asdf")
    filetab.save_as(tmp_path / "main.py")

    no_terminal.run_command(f"{utils.quote(sys.executable)} main.py", tmp_path)
    tkinter_sleep(3)
    assert "No such file or directory" in get_output(filetab)
    assert "The process failed with status 1." in get_output(filetab)

    # click the last link
    textwidget = get_output_widget(filetab)
    textwidget.mark_set("current", "link.last - 1 char")
    no_terminal._no_terminal_runners[str(filetab)]._link_manager._open_link(None)

    selected_tab = tabmanager.select()
    assert selected_tab != filetab
    assert selected_tab.path == tmp_path / "asdf.py"
    assert selected_tab.textwidget.get("sel.first", "sel.last") == "open('this does not exist')"


def test_python_unbuffered(filetab, tmp_path):
    (tmp_path / "sleeper.py").write_text(
        """
import time
print("This should show up immediately")
time.sleep(5)
"""
    )
    no_terminal.run_command(f"{utils.quote(sys.executable)} sleeper.py", tmp_path)
    tkinter_sleep(3)
    assert "This should show up immediately" in get_output(filetab)


def test_changing_current_file(filetab, tmp_path):
    filetab.textwidget.insert("end", 'with open("foo.py", "w") as f: f.write("lol")')
    filetab.save_as(tmp_path / "foo.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} foo.py", tmp_path)
    tkinter_sleep(3)
    assert filetab.textwidget.get("1.0", "end").strip() == "lol"


def test_no_previous_command_error(filetab, tmp_path, mocker):
    filetab.save_as(tmp_path / "foo.txt")
    mock = mocker.patch("tkinter.messagebox.showerror")
    get_main_window().event_generate("<<Menubar:Run/Repeat previous command>>")
    mock.assert_called_once()
    assert "press F4 to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)
