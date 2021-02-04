import random
import re
import threading
import time
import types

import pytest
import requests
from pygments.lexer import Lexer
from pygments.lexers import PythonLexer, TextLexer, get_lexer_by_name

import porcupine.plugins.pastebin as pastebin_module
from porcupine import get_main_window


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


def check_pastebin(pastebin_name):
    some_code = "import foo as bar\nprint('baz')"

    for lexer in [TextLexer, PythonLexer]:
        function = pastebin_module.pastebins[pastebin_name]
        url = function(some_code, lexer)
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
    check_pastebin('termbin.com')


@pytest.mark.pastebin_test
def test_dpaste_dot_com():
    check_pastebin('dpaste.com')


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
    monkeypatch.setitem(pastebin_module.pastebins, 'Lol', (lambda *args: 1/0))
    errordialog_calls = []
    monkeypatch.setattr(pastebin_module.utils, 'errordialog',
                        lambda *args, **kwargs: errordialog_calls.append((args, kwargs)))

    paste = pastebin_module.Paste('Lol', 'test code', PythonLexer)
    paste.start()

    while paste.please_wait_window.winfo_exists():
        paste.please_wait_window.update()

    assert len(errordialog_calls) == 1
    args, kwargs = errordialog_calls[0]
    assert args == (
        "Pasting Failed",
        "Check your internet connection and try again.\n\nHere's the full error message:",
    )
    assert 'ZeroDivisionError' in kwargs['monospace_text']
    assert 'ZeroDivisionError' in caplog.records[-1].message


def test_start_pasting_with_menubar(monkeypatch, filetab):
    called = []

    class FakePaste:
        def __init__(self, pastebin_name, code, lexer):
            self.started = 0
            assert code == ''
            assert issubclass(lexer, Lexer)
            self._pastebin_name = pastebin_name

        def start(self):
            called.append(self._pastebin_name)

    monkeypatch.setattr(pastebin_module, 'Paste', FakePaste)

    pastebin_names = list(pastebin_module.pastebins.keys())
    random.shuffle(pastebin_names)

    for name in pastebin_names:
        get_main_window().event_generate(f'<<Menubar:Share/{name}>>')
    assert called == pastebin_names
