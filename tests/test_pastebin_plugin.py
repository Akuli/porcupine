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
from pygments.lexers import PythonLexer, TextLexer, find_lexer_class_by_name

from porcupine import get_main_window, utils
from porcupine.plugins import rightclick_menu
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

    # These are wrong for whatever reason, can look into them if it bothers someone
    del syntax_choices["json-object"]
    del syntax_choices["ipython2"]
    del syntax_choices["ipython3"]
    del syntax_choices["ipythonconsole"]

    for syntax_choice in syntax_choices.keys():
        lexer_class = find_lexer_class_by_name(syntax_choice)
        assert syntax_choice == DPaste.get_dpaste_name_for_lexer_class(lexer_class)


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
    dialog = SuccessDialog("https://example.com/poop")

    dialog.clipboard_append("this junk should be gone soon")
    dialog.copy_to_clipboard()
    assert dialog.clipboard_get() == "https://example.com/poop"

    # make sure that webbrowser.open is called
    mock = mocker.patch("porcupine.plugins.pastebin.webbrowser")
    assert dialog.winfo_exists()
    dialog.open_in_browser()
    assert not dialog.winfo_exists()
    mock.open.assert_called_once_with("https://example.com/poop")

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
                assert sock.recv(1024).rstrip(b"\n") == b"hello world"
                sock.sendall(b"https://example.com/\n\0")
            nonlocal thread_done
            thread_done = True

        thread = threading.Thread(target=fake_termbin)
        thread.start()

        def fake_wait_window(success_dialog):
            assert success_dialog.title() == "Pasting Succeeded"
            assert success_dialog.url == "https://example.com/"
            success_dialog.destroy()
            nonlocal fake_wait_window_done
            fake_wait_window_done = True

        monkeypatch.setattr(tkinter.Toplevel, "wait_window", fake_wait_window)

        tabmanager.select(filetab)
        filetab.textwidget.insert("end", "hello world\n")
        filetab.textwidget.tag_add("sel", "1.0", "end")  # select all
        rightclick_menu.create_menu().invoke("Pastebin selected text to termbin.com")

        thread.join()
        get_main_window().update()
        assert thread_done and fake_wait_window_done


def test_paste_error_handling(monkeypatch, caplog, mocker, tabmanager, filetab, dont_run_in_thread):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True
    monkeypatch.setattr("porcupine.plugins.pastebin.DPASTE_URL", "ThisIsNotValidUrlStart://wat")
    mocker.patch("tkinter.messagebox.showerror")

    tabmanager.select(filetab)
    filetab.textwidget.tag_add("sel", "1.0", "end")  # select all
    rightclick_menu.create_menu().invoke("Pastebin selected text to dpaste.com")

    tkinter.messagebox.showerror.assert_called_once_with(
        "Pasting failed", "Check your internet connection or try a different pastebin."
    )


def test_invalid_return(filetab, tabmanager, mocker, caplog, dont_run_in_thread):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True
    mocker.patch("tkinter.messagebox.showerror")
    mocker.patch("porcupine.plugins.pastebin.DPaste.run").return_value = "lol"

    tabmanager.select(filetab)
    filetab.textwidget.tag_add("sel", "1.0", "end")  # select all
    rightclick_menu.create_menu().invoke("Pastebin selected text to dpaste.com")

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


def test_pasting_selected_indented_code(
    filetab, tabmanager, monkeypatch, mocker, dont_run_in_thread
):
    mocker.patch("porcupine.plugins.pastebin.ask_are_you_sure").return_value = True
    monkeypatch.setattr("tkinter.Toplevel.wait_window", tkinter.Toplevel.destroy)
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
    rightclick_menu.create_menu().invoke("Pastebin selected text to dpaste.com")
    mock_run.assert_called_once_with("bar\nif baz:\n    lol\n", PythonLexer)


def test_are_you_sure_dialog(filetab, tabmanager, tmp_path, wait_until, mocker, monkeypatch):
    mock_run = mocker.patch("porcupine.plugins.pastebin.DPaste.run")

    dialogs = []
    monkeypatch.setattr("tkinter.Toplevel.wait_window", (lambda d: dialogs.append(d)))

    tabmanager.select(filetab)
    filetab.textwidget.tag_add("sel", "1.0", "end")  # select all
    rightclick_menu.create_menu().invoke("Pastebin selected text to dpaste.com")
    filetab.save_as(tmp_path / "lolwat.py")
    rightclick_menu.create_menu().invoke("Pastebin selected text to dpaste.com")

    assert len(dialogs) == 2
    assert dialogs[0].title() == "Pastebin this file"
    assert dialogs[1].title() == "Pastebin lolwat.py"
    for d in dialogs:
        assert (
            d.nametowidget("content.label1")["text"]
            == "Do you want to send the selected text to dpaste.com?"
        )
        d.destroy()

    assert mock_run.call_count == 0  # closing the window cancels pastebinning
