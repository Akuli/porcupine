import os
import re
import socket
import threading
import time
import tkinter
import types
from http.client import RemoteDisconnected

import pytest
import requests
from pygments.lexers import PythonLexer, TextLexer, get_lexer_by_name

import porcupine.plugins.pastebin as pastebin_module
from porcupine import get_main_window, utils


@pytest.mark.pastebin_test
def test_dpaste_syntax_choices():
    # download the json data representing valid syntax choices linked from dpaste docs
    response = requests.get('https://dpaste.com/api/v2/syntax-choices/')
    response.raise_for_status()
    syntax_choices = response.json()

    # Skip 'json-object', it's wrong for whatever reason
    del syntax_choices['json-object']

    for syntax_choice in syntax_choices.keys():
        assert syntax_choice == get_lexer_by_name(syntax_choice).aliases[0]


def check_pastebin(paste_class):
    some_code = "import foo as bar\nprint('baz')"

    for lexer in [TextLexer, PythonLexer]:
        url = paste_class().run(some_code, lexer)
        assert isinstance(url, str)

        response = requests.get(url)
        response.raise_for_status()

        if response.text.strip().startswith('<!DOCTYPE'):
            # html and regexes ftw
            assert some_code in re.sub(r'<.*?>', '', response.text).replace("&#39;", "'")
        else:
            # raw url
            assert response.text.strip() == some_code.strip()


@pytest.mark.pastebin_test
def test_termbin():
    check_pastebin(pastebin_module.Termbin)


@pytest.mark.pastebin_test
def test_dpaste():
    check_pastebin(pastebin_module.DPaste)


@pytest.mark.pastebin_test   # TODO: switch to localhost HTTPS server?
def test_dpaste_canceling(monkeypatch):
    monkeypatch.setattr(pastebin_module, 'DPASTE_URL', 'https://httpbin.org/delay/3')
    paste = pastebin_module.DPaste()
    got_error = False

    def thread_target():
        nonlocal got_error
        try:
            paste.run('hello world', TextLexer)
        except RemoteDisconnected:    # the error that it raises when canceled
            got_error = True

    thread = threading.Thread(target=thread_target)
    thread.start()

    start = time.time()
    time.sleep(1)
    paste.cancel()
    thread.join()
    assert time.time() - start < 1.01
    assert got_error


def test_success_dialog(monkeypatch):
    dialog = pastebin_module.SuccessDialog('http://example.com/poop')

    dialog.clipboard_append("this junk should be gone soon")
    dialog.copy_to_clipboard()
    assert dialog.clipboard_get() == 'http://example.com/poop'

    # make sure that webbrowser.open is called
    opened = []
    monkeypatch.setattr(pastebin_module, 'webbrowser',
                        types.SimpleNamespace(open=opened.append))
    assert dialog.winfo_exists()
    dialog.open_in_browser()
    assert not dialog.winfo_exists()
    assert opened == ['http://example.com/poop']

    dialog.destroy()


def test_lots_of_stuff_with_localhost_termbin(filetab, monkeypatch, tabmanager):
    with socket.socket() as termbin:
        termbin.bind(('localhost', 0))
        termbin.listen(1)
        monkeypatch.setattr(pastebin_module, 'TERMBIN_HOST_AND_PORT', termbin.getsockname())

        thread_done = False
        fake_wait_window_done = False

        def fake_termbin():
            with termbin.accept()[0] as sock:
                assert sock.recv(1024) == b'hello world\n'
                sock.sendall(b'http://example.com/\n\0')
            nonlocal thread_done
            thread_done = True

        thread = threading.Thread(target=fake_termbin)
        thread.start()

        tabmanager.select(filetab)
        filetab.textwidget.insert('end', 'hello world\n')

        def fake_wait_window(success_dialog):
            assert success_dialog.title() == "Pasting Succeeded"
            assert success_dialog.url == 'http://example.com/'
            success_dialog.destroy()
            nonlocal fake_wait_window_done
            fake_wait_window_done = True

        monkeypatch.setattr(tkinter.Toplevel, 'wait_window', fake_wait_window)
        get_main_window().event_generate('<<Menubar:Share/termbin.com>>')

        thread.join()
        get_main_window().update()
        assert thread_done and fake_wait_window_done


@pytest.mark.skipif(
    os.getenv('GITHUB_ACTIONS') == 'true',
    reason="somehow doesn't work with gh actions")
def test_paste_error_handling(monkeypatch, caplog, mocker, tabmanager, filetab):
    monkeypatch.setattr(pastebin_module, 'DPASTE_URL', 'ThisIsNotValidUrlStart://wat')
    mocker.patch('porcupine.utils.errordialog')

    tabmanager.select(filetab)
    get_main_window().event_generate('<<Menubar:Share/dpaste.com>>')
    get_main_window().update()

    utils.errordialog.assert_called_once()
    args, kwargs = utils.errordialog.call_args
    assert args == ('Pasting Failed', "Check your internet connection and try again.\n\nHere's the full error message:")
    assert 'ThisIsNotValidUrlStart'.lower() in kwargs['monospace_text']
    assert 'ThisIsNotValidUrlStart'.lower() in caplog.records[-1].message


def test_invalid_return(filetab, monkeypatch, tabmanager, mocker):
    mocker.patch('tkinter.messagebox.showerror')
    monkeypatch.setattr(pastebin_module.DPaste, 'run', (lambda *args: 'lol'))

    tabmanager.select(filetab)
    get_main_window().event_generate('<<Menubar:Share/dpaste.com>>')
    get_main_window().update()

    tkinter.messagebox.showerror.assert_called_once_with(
        'Pasting failed', "Instead of a valid URL, dpaste.com returned 'lol'.")
