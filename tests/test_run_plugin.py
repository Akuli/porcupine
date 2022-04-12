import os
import shutil
import sys
import time
from tkinter import ttk

import pytest

from porcupine import get_main_window, get_tab_manager, utils
from porcupine.plugins.run import common, dialog, history, no_terminal, terminal


@pytest.fixture(autouse=True)
def isolated_history():
    # We don't overwrite the user's file because porcupine.dirs is monkeypatched
    path = history._get_path()
    assert not path.exists()
    yield
    try:
        path.unlink()
    except FileNotFoundError:
        pass


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


def test_unicodes(filetab, tmp_path, wait_until):
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


def test_repeat_in_another_file(tmp_path, tabmanager, mocker, monkeypatch, wait_until):
    (tmp_path / "a.py").write_text("print('aaa')")
    (tmp_path / "b.py").write_text("print('bbb')")
    a = tabmanager.open_file(tmp_path / "a.py")
    b = tabmanager.open_file(tmp_path / "b.py")

    def fake_wait_window(toplevel):
        # click run button (lol)
        widgets = [toplevel]
        while True:
            w = widgets.pop()
            if isinstance(w, ttk.Button) and w["text"] == "Run":
                w.invoke()
                break
            widgets.extend(w.winfo_children())

    actual_repeater = history.get_command_to_repeat

    def fake_repeater(*args, **kwargs):
        result = actual_repeater(*args, **kwargs)
        result.external_terminal = False
        return result

    monkeypatch.setattr("tkinter.Toplevel.wait_window", fake_wait_window)
    monkeypatch.setattr("porcupine.plugins.run.history.get_command_to_repeat", fake_repeater)

    tabmanager.select(a)
    get_main_window().event_generate("<<Run:AskAndRun0>>")
    wait_until(lambda: "aaa" in get_output())

    tabmanager.select(b)
    get_main_window().event_generate("<<Run:Repeat0>>")
    wait_until(lambda: "bbb" in get_output())


def click_last_link():
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
    assert click_last_link() == "open('this does not exist')"


def test_mypy_error_message(filetab, tabmanager, tmp_path, wait_until):
    filetab.textwidget.insert("end", "print(1 + 2)\nprint(1 + 'lol')\n")
    filetab.save_as(tmp_path / "lel.py")
    no_terminal.run_command(f"{utils.quote(sys.executable)} -m mypy lel.py", tmp_path)

    # long timeout, mypy can be slow
    wait_until((lambda: "The process failed with status 1." in get_output()), timeout=60)
    assert click_last_link() == "print(1 + 'lol')"


def test_pytest_error_message(tabmanager, tmp_path, wait_until):
    (tmp_path / "tests.py").write_text("def test_foo(asdf): pass")
    no_terminal.run_command(f"{utils.quote(sys.executable)} -m pytest tests.py", tmp_path)
    wait_until(lambda: "The process failed with status 1." in get_output())
    assert click_last_link() == "def test_foo(asdf): pass"


def test_bindcheck_message(filetab, tabmanager, tmp_path, wait_until):
    filetab.textwidget.insert("end", "asdf.bind('<Foo>', print)")
    (tmp_path / "foo").mkdir()
    filetab.save_as(tmp_path / "foo" / "foo.py")

    shutil.copy("scripts/bindcheck.py", tmp_path)
    no_terminal.run_command(f"{utils.quote(sys.executable)} bindcheck.py foo", tmp_path)

    wait_until(lambda: "The process failed with status 1." in get_output())
    assert click_last_link() == "asdf.bind('<Foo>', print)"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="commands below wouldn't work on windows even if valgrind supported windows",
)
@pytest.mark.skipif(shutil.which("gcc") is None, reason="C compiler needed")
@pytest.mark.skipif(shutil.which("valgrind") is None, reason="need valgrind")
# caplog needed to silence logging errors from langserver plugin, which tries to start clangd
def test_valgrind_error_message(filetab, tmp_path, wait_until, caplog):
    filetab.textwidget.insert(
        "end",
        r"""
#include <stdio.h>
#include <stdlib.h>
int main()
{
    char *ptr = malloc(1);
    printf("%c\n", *ptr);
    return 0;
}
""",
    )
    filetab.save_as(tmp_path / "bug.c")
    no_terminal.run_command("gcc -g bug.c", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())
    no_terminal.run_command("valgrind ./a.out", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())
    assert click_last_link() == r'    printf("%c\n", *ptr);'


@pytest.mark.skipif(shutil.which("grep") is None, reason="uses grep")
def test_grep_n_output(tabmanager, tmp_path, wait_until):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "asdf").write_text("foo")
    (tmp_path / "lol").write_text("bar")

    no_terminal.run_command("grep -n -r foo .", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())
    assert click_last_link() == "foo"

    no_terminal.run_command("grep -n -r bar .", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())
    assert click_last_link() == "bar"


def test_pyright_output(tabmanager, tmp_path, wait_until):
    (tmp_path / "_curses.pyi").write_text(
        """\
import sys
from typing import IO, Any, BinaryIO, NamedTuple, Tuple
"""
    )
    (tmp_path / "fake_pyright.py").write_text(
        """
import os
print(f"{os.getcwd()}/_curses.pyi")
print(f"  {os.getcwd()}/_curses.pyi:2:51 - error: blah blah")
"""
    )

    no_terminal.run_command(f"{utils.quote(sys.executable)} fake_pyright.py", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())
    assert click_last_link() == "from typing import IO, Any, BinaryIO, NamedTuple, Tuple"


def test_python_unbuffered(tmp_path, wait_until):
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


def test_not_line_buffered(tmp_path, wait_until):
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


def test_crlf_on_any_platform(tmp_path, wait_until):
    (tmp_path / "crlf.py").write_text(r"import sys; sys.stdout.buffer.write(b'foo\r\nbar')")
    no_terminal.run_command(f"{utils.quote(sys.executable)} crlf.py", tmp_path)
    wait_until(lambda: "foo\nbar" in get_output())


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
    shift_f5 = "⇧F5" if filetab.tk.eval("tk windowingsystem") == "aqua" else "Shift+F5"
    assert f"press {shift_f5} to choose a command" in str(mock.call_args)
    assert "then repeat it with F5" in str(mock.call_args)


def test_example_commands_of_different_filetypes(filetab, tmp_path, mocker):
    python_mock = mocker.patch("porcupine.plugins.run.terminal.run_command")
    html_mock = mocker.patch("porcupine.plugins.run.no_terminal.run_command")

    filetab.save_as(tmp_path / "hello.py")
    get_main_window().event_generate("<<Run:Repeat0>>")
    filetab.save_as(tmp_path / "asdf.html")
    get_main_window().event_generate("<<Run:Repeat0>>")

    html_path = utils.quote(str(tmp_path / "asdf.html"))
    if sys.platform == "win32":
        python_mock.assert_called_once_with("py hello.py", tmp_path)
        html_mock.assert_called_once_with(f"explorer {html_path}", tmp_path)
    else:
        opener = "open" if sys.platform == "darwin" else "x-www-browser"
        python_mock.assert_called_once_with("python3 hello.py", tmp_path)
        html_mock.assert_called_once_with(f"{opener} {html_path} >/dev/null 2>&1 &", tmp_path)


def test_cwd_entry(filetab, tmp_path):
    (tmp_path / "subdir").mkdir()
    filetab.save_as(tmp_path / "foo.txt")
    asker = dialog._CommandAsker(common.Context(filetab, 1))
    asker.command.format_var.set("echo lol")

    assert asker.cwd.format_var.get() == "{folder_path}"
    assert str(asker.run_button["state"]) == "normal"
    assert asker.get_command().format_cwd() == tmp_path

    for path in ["", ".", "..", "../..", tmp_path.name, "subdir", str(tmp_path / "foo.txt")]:
        asker.cwd.format_var.set(path)
        assert str(asker.run_button["state"]) == "disabled"

    for path in [tmp_path.parent, tmp_path, tmp_path / "subdir"]:
        asker.cwd.format_var.set(str(path))
        assert str(asker.run_button["state"]) == "normal"
        asker.get_command().format_cwd() == path

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
        rf"""
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


@pytest.mark.parametrize("use_after_idle", [True, False])
def test_smashing_f5(tmp_path, wait_until, use_after_idle):
    (tmp_path / "hello.py").write_text("print('Hello')")

    run = lambda: no_terminal.run_command(f"{utils.quote(sys.executable)} hello.py", tmp_path)
    if use_after_idle:
        get_main_window().after_idle(run)
        get_main_window().after_idle(run)
        get_main_window().after_idle(run)
    else:
        run()
        run()
        run()

    wait_until(lambda: "The process completed successfully." in get_output())
    first_line, rest = get_output().split("\n", 1)
    assert first_line.endswith("hello.py")
    assert rest == "Hello\nThe process completed successfully."


def test_stop_button(tmp_path, wait_until):
    (tmp_path / "sleeper.py").write_text("import time; print('started'); time.sleep(10)")
    no_terminal.run_command(f"{utils.quote(sys.executable)} sleeper.py", tmp_path)
    wait_until(lambda: "started" in get_output())
    no_terminal.runner.stop_button.event_generate("<Button-1>")
    wait_until(lambda: "started\nKilled.")


def test_stop_button_pressed_after_finished(tmp_path, wait_until):
    no_terminal.run_command(f"{utils.quote(sys.executable)} -c pass", tmp_path)
    wait_until(lambda: "The process completed successfully." in get_output())

    no_terminal.runner.stop_button.event_generate("<Button-1>")
    assert "Killed" not in get_output()


def test_infinite_loop(tmp_path, wait_until):
    (tmp_path / "loop.py").write_text(
        """\
i = 0
while True:
    print(i)
    i = i+1
    """
    )
    no_terminal.run_command(f"{utils.quote(sys.executable)} loop.py", tmp_path)

    wait_until(
        lambda: get_output().splitlines()[-1].isdecimal()
        and int(get_output().splitlines()[-1]) >= 2 * no_terminal.MAX_SCROLLBACK
    )
    no_terminal.runner.stop_button.event_generate("<Button-1>")
    wait_until(lambda: get_output().strip().endswith("Killed."))
    lines = get_output().strip().replace("Killed.", "").splitlines()[1:]

    assert (
        len(lines) < no_terminal.MAX_SCROLLBACK
    )  # there were more prints, but old output was removed
    start = int(lines[0])
    assert start > 0
    assert lines == [str(i) for i in range(start, start + len(lines))]
