import tkinter

import pytest

from porcupine.plugins.urls import find_urls

simple_urls = [
    "https://github.com/Akuli/porcupine/",
    "http://example.com/",
    "http://example.com/comma,stuff",
    "http://127.0.0.1:12345/foo.html",
]
parenthesized_urls = [
    "https://en.wikipedia.org/wiki/Whitespace_(programming_language)",
    "https://example.com/foo(bar)baz",
]

simple_text = """\
          URL
      bla URL
      bla URL bla
          URL bla bla
      Bla URL.
 Bla bla  URL.
 Bla bla  URL, foo and bar.
     bla "URL" bla
     bla 'URL' bla
         `URL`
         <URL>
    `foo <URL>`_           RST link
         'URL bla'
"See also URL"
        ("URL")bla
         {URL}      might occur in Tcl code, for example
"""
parenthesized_text = """\
         (URL)
         (URL )     often used with tools that don't understand parenthesized urls
        "(URL)" :)
 Bla bla (URL) bla.
 Bla bla (URL).
 Bla bla (URL.)
 Bla bla (URL, bla).
 Bla (see URL)
   [Link](URL)
   [Link](URL), foo and bar
   [Link](URL).
   [Link](URL).</small>    mixed markdown and HTML
"""


def check(url, line):
    textwidget = tkinter.Text()
    textwidget.insert("1.0", line.replace("URL", url))
    [(start, end)] = find_urls(textwidget, "1.0", "end")
    assert textwidget.index(start) == "1.10"
    assert textwidget.index(end) == f"1.{10 + len(url)}"
    textwidget.destroy()


@pytest.mark.parametrize("url", simple_urls)
@pytest.mark.parametrize("line", (simple_text + parenthesized_text).splitlines())
def test_find_urls_with_simple_urls(url, line):
    check(url, line)


@pytest.mark.parametrize("url", simple_urls + parenthesized_urls)
@pytest.mark.parametrize("line", simple_text.splitlines())
def test_find_urls_with_parenthesized_urls(url, line):
    check(url, line)


@pytest.mark.parametrize("url", parenthesized_urls)
@pytest.mark.parametrize("line", parenthesized_text.splitlines())
@pytest.mark.xfail(strict=True)
def test_parenthesized_urls_in_parenthesized_text(url, line):
    check(url, line)
