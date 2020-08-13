import random
import threading
import time
import tkinter
import types

import pytest
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from porcupine import get_main_window
import porcupine.plugins.pastebin as pastebin_module


BLAH_BLAH = "Hello World!\nThis is a test.\n"


def check_pastebin(pastebin_name):
    @pytest.mark.pastebin_test
    def test_function():
        function = pastebin_module.pastebins[pastebin_name]
        url = function(BLAH_BLAH, "/tmp/asd.py")
        assert isinstance(url, str)

        response = requests.get(url)
        response.raise_for_status()
        assert BLAH_BLAH in response.text.replace('\r\n', '\n')

    return test_function


test_termbin = check_pastebin('termbin.com')
test_dpaste_dot_org = check_pastebin('dpaste.org')


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


def test_paste_class(monkeypatch, filetab):
    original_thread = threading.current_thread()

    called = False

    def lol_pastebin(code, path):
        nonlocal called
        assert not called, "the pastebin function was called more than once"
        called = True

        assert code == 'test code'
        assert path == 'test path'
        assert threading.current_thread() is not original_thread
        time.sleep(1)   # try to cover corner cases
        return 'test url'

    monkeypatch.setitem(pastebin_module.pastebins, 'Lol', lol_pastebin)

    all_done = False

    def fake_wait_window_method_which_is_called_when_everything_is_done(self):
        nonlocal all_done
        assert self.title() == "Pasting Succeeded"
        self.destroy()
        all_done = True

    monkeypatch.setattr(
        pastebin_module.SuccessDialog, 'wait_window',
        fake_wait_window_method_which_is_called_when_everything_is_done)

    paste = pastebin_module.Paste('Lol', 'test code', 'test path')
    paste.start()
    while not all_done:
        filetab.update()


# this test assumes that utils.run_in_thread works
def test_paste_error_handling(monkeypatch, caplog):
    traceback_string = "Traceback (most recent call last):\nblah blah blah"
    paste = pastebin_module.Paste('Lol', 'test code', 'test path')

    # because i'm lazy
    paste.please_wait_window = tkinter.Toplevel()
    monkeypatch.setattr(pastebin_module, 'tk_busy_forget', (lambda: None))

    errordialog_calls = []
    monkeypatch.setattr(pastebin_module, 'utils', types.SimpleNamespace(
        errordialog=lambda *args, **kwargs: {
            errordialog_calls.append(args),
            errordialog_calls.append(kwargs),
        }))

    caplog.clear()
    paste.done_callback(False, traceback_string)

    assert errordialog_calls == [
        ("Pasting Failed",
         "Check your internet connection and try again.\n\n" +
         "Here's the full error message:"),
        {'monospace_text': traceback_string},
    ]
    assert len(caplog.records) == 1
    assert traceback_string in caplog.records[0].message


def test_start_pasting_with_menubar(monkeypatch, filetab):
    called = []

    class FakePaste:
        def __init__(self, pastebin_name, code, path):
            self.started = 0
            assert code == ''
            assert path is None     # because the filetab hasn't been saved
            self._pastebin_name = pastebin_name

        def start(self):
            called.append(self._pastebin_name)

    monkeypatch.setattr(pastebin_module, 'Paste', FakePaste)

    pastebin_names = list(pastebin_module.pastebins.keys())
    random.shuffle(pastebin_names)

    for name in pastebin_names:
        get_main_window().event_generate(f'<<Menubar:Share/{name}>>')
    assert called == pastebin_names
