import os
import shutil
import sys
import time
from typing import Any, List

import pytest

from porcupine import get_main_window, get_tab_manager, utils
from porcupine.plugins.run import dialog, no_terminal, settings, terminal


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
def test_external_terminal(filetab, tmp_path, fake_runner, wait_until):
    filetab.textwidget.insert("end", "open('file', 'w').write('hello')")
    filetab.save_as(tmp_path / "hello.py")
    get_main_window().event_generate("<<Run:Repeat0>>")
    wait_until(lambda: (tmp_path / "file").exists() and (tmp_path / "file").read_text() == "hello")


def get_output():
    return no_terminal.runner.textwidget.get("1.0", "end - 1 char")


def test_output_in_porcupine_window(filetab, tmp_path, wait_until):
    filetab.textwidget.insert(
        "end",
        r"""
print("123")
print("örkki")

import sys

# Test error handling for badly printed bytes
# All bytes that are invalid utf-8 AND invalid cp1252: 81, 8D, 8F, 90, 9D
sys.stderr.buffer.write(b'\x81')
print()

# unicodes beyond U+FFFF are not supported by tk
# can't test this on windows because cp1252 doesn't go beyond U+FFFF
if sys.platform != "win32":
    print("\N{pile of poo}")
""",
    )
    filetab.save_as(tmp_path / "lol.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} lol.py", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())

    assert "123" in get_output()
    assert "örkki" in get_output()
    if sys.platform == "win32":
        assert get_output().count("\N{replacement character}") == 1
    else:
        assert get_output().count("\N{replacement character}") == 2


def click_last_link(filetab):
    textwidget = no_terminal.runner.textwidget
    textwidget.mark_set("current", "link.last - 1 char")
    no_terminal.runner._link_manager._open_link(None)
    return get_tab_manager().select().textwidget.get("sel.first", "sel.last")


def test_python_error_message(filetab, tabmanager, tmp_path, wait_until):
    (tmp_path / "asdf.py").write_text("print(1)\nopen('this does not exist')\nprint(2)\n")
    filetab.textwidget.insert("end", "import asdf")
    filetab.save_as(tmp_path / "main.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} main.py", tmp_path)

    wait_until(lambda: "The process failed with status 1." in get_output())
    assert "No such file or directory" in get_output()
    assert click_last_link(filetab) == "open('this does not exist')"


def test_mypy_error_message(filetab, tabmanager, tmp_path, wait_until):
    filetab.textwidget.insert("end", "print(1 + 2)\nprint(1 + 'lol')\n")
    filetab.save_as(tmp_path / "lel.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} -m mypy lel.py", tmp_path)

    # long timeout, mypy can be slow
    wait_until((lambda: "The process failed with status 1." in get_output()), timeout=15)
    assert click_last_link(filetab) == "print(1 + 'lol')"


def test_bindcheck_message(filetab, tabmanager, tmp_path, wait_until):
    filetab.textwidget.insert("end", "asdf.bind('<Foo>', print)")
    (tmp_path / "foo").mkdir()
    filetab.save_as(tmp_path / "foo" / "foo.py")

    shutil.copy("scripts/bindcheck.py", tmp_path)
    no_terminal.run_command(f"{utils.quote(sys.executable)} bindcheck.py foo", tmp_path)

    wait_until(lambda: "The process failed with status 1." in get_output())
    assert click_last_link(filetab) == "asdf.bind('<Foo>', print)"


def test_python_unbuffered(filetab, tmp_path, wait_until):
    (tmp_path / "sleeper.py").write_text(
        """
import time
print("This should show up immediately")
time.sleep(10)
"""
    )
    start = time.monotonic()
    no_terminal.run_command(f"{utils.quote(sys.executable)} sleeper.py", tmp_path)
    wait_until(lambda: "This should show up immediately" in get_output())
    end = time.monotonic()
    assert end - start < 8


def test_not_line_buffered(filetab, tmp_path, wait_until):
    (tmp_path / "sleeper.py").write_text(
        """
import time
print("This should show up immediately", end="", flush=True)
time.sleep(10)
"""
    )
    start = time.monotonic()
    no_terminal.run_command(f"{utils.quote(sys.executable)} sleeper.py", tmp_path)
    wait_until(lambda: "This should show up immediately" in get_output())
    end = time.monotonic()
    assert end - start < 8


def test_changing_current_file(filetab, tmp_path, wait_until):
    filetab.textwidget.insert("end", 'with open("foo.py", "w") as f: f.write("lol")')
    filetab.save_as(tmp_path / "foo.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} foo.py", tmp_path)
    wait_until(lambda: filetab.textwidget.get("1.0", "end").strip() == "lol")


def test_no_previous_command_error(filetab, tmp_path, mocker):
    filetab.save_as(tmp_path / "foo.txt")
    mock = mocker.patch("tkinter.messagebox.showerror")
    get_main_window().event_generate("<<Run:Repeat0>>")

    mock.assert_called_once()
    if filetab.tk.eval("tk windowingsystem") == "aqua":
        assert "press ⇧F5 to choose a command" in str(mock.call_args)
    else:
        assert "press Shift+F5 to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)


def test_cwd_entry(filetab, tmp_path):
    (tmp_path / "subdir").mkdir()
    filetab.save_as(tmp_path / "foo.txt")
    asker = dialog._CommandAsker(
        file_path=(tmp_path / "foo.txt"), project_path=tmp_path, suggestions=[], initial_key_id=1
    )
    asker.command.format_var.set("echo lol")

    assert asker.cwd.format_var.get() == "{folder_path}"
    assert asker.cwd.value == tmp_path
    assert str(asker.run_button["state"]) == "normal"

    for path in ["", ".", "..", "../..", tmp_path.name, "subdir", str(tmp_path / "foo.txt")]:
        asker.cwd.format_var.set(path)
        assert asker.cwd.value is None
        assert str(asker.run_button["state"]) == "disabled"

    for path in [tmp_path.parent, tmp_path, tmp_path / "subdir"]:
        asker.cwd.format_var.set(str(path))
        assert asker.cwd.value == path
        assert str(asker.run_button["state"]) == "normal"

    asker.window.destroy()


SMALL_TIME = 0.1


def size_is_changing(path):
    old_size = path.stat().st_size
    time.sleep(2 * SMALL_TIME)
    new_size = path.stat().st_size
    return old_size != new_size


@pytest.mark.skipif(sys.platform == "darwin", reason="somehow fails github actions on macos")
def test_previous_process_dies(tmp_path, wait_until):
    (tmp_path / "hello.py").write_text("print('Hello')")
    (tmp_path / "killed.py").write_text(
        fr"""
import time
while True:
    with open("out.txt", "a") as file:
        file.write("Still alive\n")
    time.sleep({SMALL_TIME})
"""
    )

    no_terminal.run_command(f"{utils.quote(sys.executable)} killed.py", tmp_path)
    wait_until(lambda: (tmp_path / "out.txt").exists())
    assert size_is_changing(tmp_path / "out.txt")

    no_terminal.run_command(f"{utils.quote(sys.executable)} hello.py", tmp_path)
    wait_until(lambda: "Hello" in get_output())
    assert not size_is_changing(tmp_path / "out.txt")


def test_smashing_f5(tmp_path, wait_until):
    (tmp_path / "hello.py").write_text("print('Hello')")
    no_terminal.run_command(f"{utils.quote(sys.executable)} hello.py", tmp_path)
    no_terminal.run_command(f"{utils.quote(sys.executable)} hello.py", tmp_path)
    no_terminal.run_command(f"{utils.quote(sys.executable)} hello.py", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())

    first_line, rest = get_output().split("\n", 1)
    assert first_line.endswith("hello.py")
    assert rest == "Hello\nThe process completed successfully."
