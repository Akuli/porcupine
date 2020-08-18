import tkinter

from porcupine import get_main_window
from porcupine.plugins.urls import find_urls


def test_find_urls_basic(porcusession):
    text = tkinter.Text(get_main_window())
    urls = [
        'https://github.com/Akuli/porcupine/',
        'http://example.com/',
        'http://example.com/comma,stuff',
    ]
    for url in urls:
        text.delete('1.0', 'end')
        text.insert('end', '''\
          URL
          URL bla bla
"See also URL"
         'URL bla'
         (URL)
         (URL )     often used with tools that don't understand parenthesized urls
         {URL}      might occur in Tcl code, for example
         <URL>
        ("URL")bla
        "(URL)" :)
 Bla bla (URL, bla)
 Bla (see URL)
      See URL.
      See URL, foo and bar.
   [Link](URL)
   [Link](URL), foo and bar
   [Link](URL).
'''.replace('URL', url))
        assert [(text.index(start), text.index(end)) for start, end in find_urls(text)] == [
            (f'{lineno}.10', f'{lineno}.{10 + len(url)}')
            for lineno in range(1, 18)
        ]


# urls with parentheses in them don't need to work in all cases, just very basic support wanted
def test_url_containing_parens(porcusession):
    for url in ['https://en.wikipedia.org/wiki/Whitespace_(programming_language)', 'https://example.com/foo(bar)baz']:
        text = tkinter.Text(get_main_window())
        text.insert('1.0', f'''\
 bla {url}
 bla {url} bla
 Bla {url}.
bla "{url}" bla
bla '{url}' bla
''')
        assert [(text.index(start), text.index(end)) for start, end in find_urls(text)] == [
            (f'{lineno}.5', f'{lineno}.{5 + len(url)}')
            for lineno in range(1, 6)
        ]
