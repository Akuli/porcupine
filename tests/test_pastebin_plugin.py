import random
import re
import threading
import time
import tkinter
import traceback
import types

import pytest
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

import porcupine.plugins.pastebin as pastebin_module
from porcupine import actions


BLAH_BLAH = "Hello World!\nThis is a test.\n"


def do_paste(pastebin_name):
    function = pastebin_module.pastebins[pastebin_name]
    url = function(BLAH_BLAH, "/tmp/asd.py")
    assert isinstance(url, str)
    return url


def check_raw_url(url):
    response = requests.get(url)
    response.raise_for_status()

    # line end replace because some pastebins
    assert response.text.replace('\r\n', '\n') == BLAH_BLAH


@pytest.mark.pastebin_test
def test_termbin():
    url = do_paste('termbin.com')
    assert re.fullmatch(r'http://termbin.com/.+', url)
    check_raw_url(url)


@pytest.mark.pastebin_test
def test_dpaste_dot_com():
    url = do_paste('dpaste.com')
    assert re.fullmatch(r'http://dpaste.com/.+', url)
    check_raw_url(url + '.txt')


@pytest.mark.pastebin_test
def test_dpaste_dot_de():
    url = do_paste('dpaste.de')
    assert re.fullmatch(r'https://dpaste.de/.+', url)
    check_raw_url(url + '/raw')


# TODO: test ghostbin, its API doesn't seem to work today


# Paste ofCode doesn't seem to have any kind of nice text-only urls, so parsing
# with bs4 is the best option
@pytest.mark.pastebin_test
@pytest.mark.skipif(BeautifulSoup is not None, reason="bs4 is installed")
def test_paste_of_code_without_bs4():
    url = do_paste('Paste ofCode')
    print()
    print("Cannot check if the created Paste ofCode paste contains the "
          "correct content. Please check it yourself:")
    print()
    print("  ", url)
    print()
    print("The content should be:")
    print(BLAH_BLAH)


@pytest.mark.pastebin_test
@pytest.mark.skipif(BeautifulSoup is None, reason="bs4 is not installed")
def test_paste_of_code_with_bs4():
    url = do_paste('Paste ofCode')

    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    pre = soup.find_all('pre')[-1]

    # the pre contains some newlines as is, but also some spans for syntax
    # highlighting
    texts = [content if isinstance(content, str) else content.text
             for content in pre]
    assert ''.join(texts).strip() == BLAH_BLAH.strip()


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


def test_start_pasting_with_actions(monkeypatch, filetab):
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
        action = actions.get_action('Share/%s' % name)
        assert action.enabled
        action.callback()
    assert called == pastebin_names
