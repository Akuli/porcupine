import pytest
import shutil
import sys
import time
from typing import List, Any

from porcupine import get_main_window
from porcupine.plugins.run import settings, terminal


def copy_file_with_modification(source, destination, old_string, new_string):
    content = source.read_text()
    assert content.count(old_string) == 1
    assert not destination.exists()
    destination.write_text(content.replace(old_string, new_string))


@pytest.fixture
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


def test_external_terminal(filetab, tmp_path, monkeypatch, fake_runner, isolated_history):
    filetab.textwidget.insert(
        "end",
        r"""
from pathlib import Path
Path('file').write_text('hello')
""",
    )
    filetab.save_as(tmp_path / "hello.py")
    get_main_window().event_generate("<<Menubar:Run/Repeat previous command>>")
    time.sleep(0.5)
    assert (tmp_path / "file").read_text() == "hello"


def test_no_previous_command_error(filetab, tmp_path, mocker, isolated_history):
    filetab.save_as(tmp_path / "foo.txt")
    mock = mocker.patch("tkinter.messagebox.showerror")
    get_main_window().event_generate("<<Menubar:Run/Repeat previous command>>")
    mock.assert_called_once()
    assert "press F4 to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)
