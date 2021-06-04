import tkinter

from porcupine import get_main_window
from porcupine.plugins.urls import find_urls


def test_find_urls():
    text = tkinter.Text(get_main_window())
    urls = [
        'https://github.com/Akuli/porcupine/',
        'http://example.com/',
        'http://example.com/comma,stuff',
    ]
    test_cases = '''\
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
 Bla bla  URL.
 Bla bla  URL, foo and bar.
 Bla bla (URL) bla.
 Bla bla (URL).
 Bla bla (URL.)
 Bla bla (URL, bla).
 Bla (see URL)
   [Link](URL)
   [Link](URL), foo and bar
   [Link](URL).
   [Link](URL).</small>    mixed markdown and HTML
    `foo <URL>`_           RST link
'''.splitlines()

    for url in urls:
        for line in test_cases:
            text.delete('1.0', 'end')
            text.insert('1.0', line.replace('URL', url))

            [(start, end)] = find_urls(text, '1.0', 'end')
            assert text.index(start) == '1.10'
            assert text.index(end) == f'1.{10 + len(url)}'


# urls with parentheses in them don't need to work in all cases, just very basic support wanted
def test_url_containing_parens():
    for url in ['https://en.wikipedia.org/wiki/Whitespace_(programming_language)', 'https://example.com/foo(bar)baz']:
        text = tkinter.Text(get_main_window())
        text.insert('1.0', f'''\
 bla {url}
 bla {url} bla
 Bla {url}.
bla "{url}" bla
bla '{url}' bla
''')
        assert [(text.index(start), text.index(end)) for start, end in find_urls(text, '1.0', 'end')] == [
            (f'{lineno}.5', f'{lineno}.{5 + len(url)}')
            for lineno in range(1, 6)
        ]
