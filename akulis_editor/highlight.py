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

    def __init__(self, textwidget):
        """Initialize the syntax highlighter.

        The textwidget should have string, keyword, exception, builtin,
        comment and decorator tags.
        """
        self._widget = textwidget

        # copy 'string' tag to 'multiline-string', this is a separate
        # tag because multiline strings are highlighted separately
        options = {}
        for name in self._widget.tag_config('string'):
            options[name] = self._widget.tag_cget('string', name)
        self._widget.tag_config('multiline-string', **options)

        self._line_highlights = []  # [(regex, tag), ...]

        for name in keyword.kwlist:
            regex = re.compile(IDENTIFIER % name)
            self._line_highlights.append((regex, 'keyword'))

        # True, False, None and probably some other things (i'm too lazy
        # to check lol) are in both keyword.kwlist and dir(builtins). We
        # want them in keywords, not in builtins.
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

        # This will be used for removing old tags in do_visible_lines().
        # The same tag can be added multiple times, but it needs to be
        # removed only once.
        self._line_highlight_tags = set()
        for regex, tag in self._line_highlights:
            self._line_highlight_tags.add(tag)

    def do_line(self, lineno):
        """Do all one-line highlighting of a line."""
        line_start = '%d.0' % lineno
        line_end = '%d.0+1l' % lineno

        for tag in self._line_highlight_tags:
            self._widget.tag_remove(tag, line_start, line_end)

        text = self._widget.get(line_start, line_end).rstrip('\n')
        for regex, tag in self._line_highlights:
            for match in regex.finditer(text):
                start = '{}.0+{}c'.format(lineno, match.start())
                end = '{}.0+{}c'.format(lineno, match.end())
                self._widget.tag_add(tag, start, end)

    def do_lines(self, first_lineno, last_lineno):
        """Do all one-line highlighting between two lines."""
        for lineno in range(first_lineno, last_lineno+1):
            self.do_line(lineno)

    def do_multiline(self):
        """Do all multiline highlighting needed.

        Currently only multiline strings need this.
        """
        text = self._widget.get('0.0', 'end-1c')
        self._widget.tag_remove('multiline-string', '0.0', 'end-1c')
        for match in MULTILINE_STRING.finditer(text):
            start, end = map('0.0+{}c'.format, match.span())
            self._widget.tag_add('multiline-string', start, end)
