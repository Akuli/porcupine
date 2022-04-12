import logging
import re
import socket
import threading
import time
import tkinter
import traceback
from http.client import RemoteDisconnected

import pytest
import requests
from pygments.lexers import PythonLexer, TextLexer, get_lexer_by_name

from porcupine import get_main_window, utils
from porcupine.plugins.pastebin import DPaste, SuccessDialog, Termbin


# utils.run_in_thread() can make tests fragile
@pytest.fixture
def dont_run_in_thread(monkeypatch):
    def func(blocking_function, done_callback, check_interval_ms=69, daemon=True):
        try:
            result = blocking_function()
        except Exception:
            done_callback(False, traceback.format_exc())
        else:
            done_callback(True, result)

    monkeypatch.setattr(utils, "run_in_thread", func)


@pytest.mark.pastebin_test
def test_dpaste_syntax_choices():
    # download the json data representing valid syntax choices linked from dpaste docs
    response = requests.get("https://dpaste.com/api/v2/syntax-choices/")
    response.raise_for_status()
    syntax_choices = response.json()

    # These are wrong for whatever reason (different pygments versions?)
    del syntax_choices["amdgpu"]
    del syntax_choices["ansys"]
    del syntax_choices["asc"]
    del syntax_choices["cddl"]
    del syntax_choices["futhark"]
    del syntax_choices["gcode"]
    del syntax_choices["graphviz"]
    del syntax_choices["gsql"]
    del syntax_choices["ipython2"]
    del syntax_choices["ipython3"]
    del syntax_choices["ipythonconsole"]
    del syntax_choices["jslt"]
    del syntax_choices["json-object"]
    del syntax_choices["kuin"]
    del syntax_choices["meson"]
    del syntax_choices["nestedtext"]
    del syntax_choices["nodejsrepl"]
    del syntax_choices["omg-idl"]
    del syntax_choices["output"]
    del syntax_choices["procfile"]
    del syntax_choices["smithy"]
    del syntax_choices["teal"]
    del syntax_choices["ti"]
    del syntax_choices["wast"]

    for syntax_choice in syntax_choices.keys():
        assert syntax_choice == get_lexer_by_name(syntax_choice).aliases[0]


@pytest.mark.pastebin_test
@pytest.mark.parametrize("paste_class", [DPaste, Termbin])
def test_pastebin(paste_class):
    some_code = "import foo as bar\nprint('baz')"

    for lexer in [TextLexer, PythonLexer]:
        url = paste_class().run(some_code, lexer)
        assert isinstance(url, str)

        response = requests.get(url)
        response.raise_for_status()

        if response.text.strip().startswith("<!DOCTYPE"):
            # html and regexes ftw
            assert some_code in re.sub(r"<.*?>", "", response.text).replace("&#39;", "'")
        else:
            # raw url
            assert response.text.strip() == some_code.strip()


@pytest.mark.pastebin_test  # TODO: switch to localhost HTTPS server?
def test_dpaste_canceling(monkeypatch):
    monkeypatch.setattr("porcupine.plugins.pastebin.DPASTE_URL", "https://httpbin.org/delay/3")
    paste = DPaste()
    got_error = False

    def thread_target():
        nonlocal got_error
        try:
            paste.run("hello world", TextLexer)
        except RemoteDisconnected:  # the error that it raises when canceled
            got_error = True

    thread = threading.Thread(target=thread_target)
    thread.start()

    start = time.time()
    time.sleep(1)
    paste.cancel()
    thread.join()
    assert time.time() - start < 1.05
    assert got_error


def test_success_dialog(mocker):
    dialog = SuccessDialog("http://example.com/poop")

    dialog.clipboard_append("this junk should be gone soon")
    dialog.copy_to_clipboard()
    assert dialog.clipboard_get() == "http://example.com/poop"

    # make sure that webbrowser.open is called
    mock = mocker.patch("porcupine.plugins.pastebin.webbrowser")
    assert dialog.winfo_exists()
    dialog.open_in_browser()
    assert not dialog.winfo_exists()
    mock.open.assert_called_once_with("http://example.com/poop")

    dialog.destroy()


def test_lots_of_stuff_with_localhost_termbin(
    filetab, monkeypatch, mocker, tabmanager, dont_run_in_thread
):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True

    with socket.socket() as termbin:
        termbin.settimeout(5)
        termbin.bind(("localhost", 0))
        termbin.listen(1)
        monkeypatch.setattr(
            "porcupine.plugins.pastebin.TERMBIN_HOST_AND_PORT", termbin.getsockname()
        )

        thread_done = False
        fake_wait_window_done = False

        def fake_termbin():
            with termbin.accept()[0] as sock:
                assert sock.recv(1024) == b"hello world\n"
                sock.sendall(b"http://example.com/\n\0")
            nonlocal thread_done
            thread_done = True

        thread = threading.Thread(target=fake_termbin)
        thread.start()

        tabmanager.select(filetab)
        filetab.textwidget.insert("end", "hello world\n")

        def fake_wait_window(success_dialog):
            assert success_dialog.title() == "Pasting Succeeded"
            assert success_dialog.url == "http://example.com/"
            success_dialog.destroy()
            nonlocal fake_wait_window_done
            fake_wait_window_done = True

        monkeypatch.setattr(tkinter.Toplevel, "wait_window", fake_wait_window)
        get_main_window().event_generate("<<Menubar:Pastebin/termbin.com>>")

        thread.join()
        get_main_window().update()
        assert thread_done and fake_wait_window_done


def test_paste_error_handling(monkeypatch, caplog, mocker, tabmanager, filetab, dont_run_in_thread):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True
    monkeypatch.setattr("porcupine.plugins.pastebin.DPASTE_URL", "ThisIsNotValidUrlStart://wat")
    mocker.patch("tkinter.messagebox.showerror")

    tabmanager.select(filetab)
    get_main_window().event_generate("<<Menubar:Pastebin/dpaste.com>>")

    tkinter.messagebox.showerror.assert_called_once_with(
        "Pasting failed", "Check your internet connection or try a different pastebin."
    )


def test_invalid_return(filetab, tabmanager, mocker, caplog, dont_run_in_thread):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True
    mocker.patch("tkinter.messagebox.showerror")
    mocker.patch("porcupine.plugins.pastebin.DPaste.run").return_value = "lol"

    tabmanager.select(filetab)
    get_main_window().event_generate("<<Menubar:Pastebin/dpaste.com>>")

    tkinter.messagebox.showerror.assert_called_once_with(
        "Pasting failed", "Instead of a valid URL, dpaste.com returned 'lol'."
    )
    assert caplog.record_tuples == [
        (
            "porcupine.plugins.pastebin",
            logging.ERROR,
            "pastebin 'dpaste.com' returned invalid url: 'lol'",
        )
    ]


def test_pasting_selected_indented_code(filetab, tabmanager, mocker, dont_run_in_thread):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True
    mocker.patch("tkinter.Toplevel.wait_window")
    mock_run = mocker.patch("porcupine.plugins.pastebin.DPaste.run")
    mock_run.return_value = "https://foobar"

    filetab.textwidget.insert(
        "1.0",
        """\
if foo:
    bar
    if baz:
        lol
""",
    )
    filetab.textwidget.tag_add("sel", "2.0", "5.0")

    tabmanager.select(filetab)
    get_main_window().event_generate("<<Menubar:Pastebin/dpaste.com>>")
    mock_run.assert_called_once_with("bar\nif baz:\n    lol\n", PythonLexer)


def test_are_you_sure_dialog(filetab, tmp_path, wait_until, mocker, monkeypatch):
    mock_run = mocker.patch("porcupine.plugins.pastebin.DPaste.run")

    dialogs = []
    monkeypatch.setattr("tkinter.Toplevel.wait_window", (lambda d: dialogs.append(d)))

    get_main_window().event_generate("<<Menubar:Pastebin/dpaste.com>>")
    filetab.save_as(tmp_path / "lolwat.py")
    get_main_window().event_generate("<<Menubar:Pastebin/dpaste.com>>")

    assert len(dialogs) == 2
    assert dialogs[0].title() == "Pastebin this file"
    assert dialogs[1].title() == "Pastebin lolwat.py"
    assert (
        dialogs[0].nametowidget("content.label1")["text"]
        == "Do you want to send the content of this file to dpaste.com?"
    )
    assert (
        dialogs[1].nametowidget("content.label1")["text"]
        == "Do you want to send the content of lolwat.py to dpaste.com?"
    )

    for d in dialogs:
        d.destroy()
    assert mock_run.call_count == 0  # closing the window cancels pastebinning
