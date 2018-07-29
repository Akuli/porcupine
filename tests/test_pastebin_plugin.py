import re
import types

import pytest
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

import porcupine.plugins.pastebin as pastebin_module


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
# TODO: get rid of github gist, they stopped supporting anonymous gists at some
#       point and i don't feel like using their auth stuff because many other
#       good pastebins are also supported


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
