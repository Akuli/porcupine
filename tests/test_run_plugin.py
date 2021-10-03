import os
import shutil
import sys
import time
from typing import Any, List

import pytest

from porcupine import get_main_window, utils
from porcupine.plugins.run import no_terminal, settings, terminal


@pytest.fixture
def isolated_history(autouse=True):
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
    time.sleep(1)
    assert (tmp_path / "file").read_text() == "hello"


def tkinter_sleep(delay):
    end = time.time() + delay
    while time.time() < end:
        get_main_window().update()


def test_output_in_porcupine_window(filetab, tmp_path):
    (tmp_path / "asdf.py").write_text("open('this does not exist')")
    filetab.textwidget.insert("end", "import asdf")
    filetab.save_as(tmp_path / "main.py")

    no_terminal.run_command(f"{utils.quote(sys.executable)} main.py", tmp_path)
    output_textwidget = filetab.bottom_frame.nametowidget("run_output")
    tkinter_sleep(1)
    assert "No such file or directory" in output_textwidget.get("1.0", "end")
    assert "The process failed with status 1." in output_textwidget.get("1.0", "end")


def test_no_previous_command_error(filetab, tmp_path, mocker):
    filetab.save_as(tmp_path / "foo.txt")
    mock = mocker.patch("tkinter.messagebox.showerror")
    get_main_window().event_generate("<<Menubar:Run/Repeat previous command>>")
    mock.assert_called_once()
    assert "press F4 to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)
