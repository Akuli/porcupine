# Copyright (c) 2017 Akuli

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""The syntax highlighting."""

import builtins
import keyword
import re

# These are stupid and don't handle all corner cases, but most of the
# time these are good enough.
IDENTIFIER = r'\b%s\b'
COMMENT = re.compile(r'#.*$')
STRING = re.compile(r"'.*?'" + '|' + r'".*?"')
MULTILINE_STRING = re.compile(r'""".*?"""' + '|' + r"'''.*?'''", re.DOTALL)
# It's important to stop at ( because it's possible to do this:
#   @some_decorator(arg1, arg2,
#                   arg3, arg4)
DECORATOR = re.compile(r'^\s*@[^\(]+')


class SyntaxHighlighter:

    def __init__(self, textwidget, settings):
        """Initialize the syntax highlighter."""
        self._widget = textwidget

        for name in ['keyword', 'exception', 'builtin', 'string',
                     'comment', 'decorator']:
            self._widget.tag_config(name, foreground=settings['colors'][name])
        # this is a separate tag because multiline strings are
        # highlighted separately
        self._widget.tag_config('multiline-string',
                                foreground=settings['colors']['string'])

        self._line_highlights = []  # [(regex, tag), ...]
        for name in keyword.kwlist:
            regex = re.compile(IDENTIFIER % name)
            self._line_highlights.append((regex, 'keyword'))
        # True, False, None and probably some other things are in both
        # keyword.kwlist and dir(builtins). We want them in keywords, not in
        # builtins.
        for name in set(dir(builtins)) - set(keyword.kwlist):
            if name.startswith('_'):
                continue
            regex = re.compile(IDENTIFIER % name)
            value = getattr(builtins, name)
            if isinstance(value, type) and issubclass(value, Exception):
                self._line_highlights.append((regex, 'exception'))
            else:
                self._line_highlights.append((regex, 'builtin'))
        self._line_highlights.append((STRING, 'string'))
        self._line_highlights.append((COMMENT, 'comment'))
        self._line_highlights.append((DECORATOR, 'decorator'))

        # This will be used for removing old tags in highlight_line().
        # The same tag can be added multiple times, but removing it multiple
        # times screws things up.
        self._line_highlight_tags = set()
        for regex, tag in self._line_highlights:
            self._line_highlight_tags.add(tag)

    def highlight_line(self, lineno=None):
        """Do all one-line highlighting needed."""
        # This must be fast because this is ran on (almost) every keypress.
        if lineno is None:
            # use cursor's line number
            lineno = int(self._widget.index('insert').split('.')[0])
        line_start = '%d.0' % lineno
        line_end = '%d.0+1l' % lineno
        text = self._widget.get(line_start, line_end).rstrip('\n')
        for tag in self._line_highlight_tags:
            self._widget.tag_remove(tag, line_start, line_end)
        for regex, tag in self._line_highlights:
            for match in regex.finditer(text):
                # % formatting is faster than .format() so we use it here
                # even though '%dc' looks kind of odd
                start = '%s.0+%dc' % (lineno, match.start())
                end = '%d.0+%dc' % (lineno, match.end())
                self._widget.tag_add(tag, start, end)

    def highlight_multiline(self):
        """Do all multiline highlighting needed.

        Currently only multiline strings need this.
        """
        text = self._widget.get('0.0', 'end-1c')
        self._widget.tag_remove('multiline-string', '0.0', 'end-1c')
        for match in MULTILINE_STRING.finditer(text):
            start, end = map('0.0+{}c'.format, match.span())
            self._widget.tag_add('multiline-string', start, end)

    def highlight_all(self):
        """Highlight everything.

        For performance reasons, it's recommended to use highlight_line() or
        highlight_multiline() instead when calling one of them is enough.
        """
        linecount = int(self._widget.index('end-1c').split('.')[0])
        for lineno in range(1, linecount + 1):
            self.highlight_line(lineno)
        self.highlight_multiline()
