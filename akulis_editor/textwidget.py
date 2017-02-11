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

"""The big text widget in the middle of the editor."""

import builtins
import keyword
import re
import tkinter as tk


class EditorText(tk.Text):

    def __init__(self, master, editor, **kwargs):
        self.editor = editor
        self.settings = editor.settings
        colorsettings = self.settings['colors']
        fg = colorsettings['foreground']
        super().__init__(
            master, foreground=fg, selectbackground=fg,
            insertbackground=fg, background=colorsettings['background'],
            undo=True, maxundo=self.settings['editing'].getint('maxundo'),
            blockcursor=self.settings['editing'].getboolean('blockcursor'),
            **kwargs)

        for name in ['keyword', 'exception', 'builtin', 'string', 'comment']:
            self.tag_config(name, foreground=colorsettings[name])
        # this is a separate tag because multiline strings are
        # highlighted separately
        self.tag_config('multiline-string',
                        foreground=colorsettings['string'])

        self._line_highlights = []  # [(regex, tag), ...]
        # True, False, None and probably some other things are in both
        # keyword.kwlist and dir(builtins). We want builtins to take
        # precedence.
        for name in set(keyword.kwlist) - set(dir(builtins)):
            regex = re.compile(self.settings['regexes']['identifier'] % name)
            self._line_highlights.append((regex, 'keyword'))
        for name in dir(builtins):
            if name.startswith('_'):
                continue
            regex = re.compile(self.settings['regexes']['identifier'] % name)
            value = getattr(builtins, name)
            if isinstance(value, type) and issubclass(value, Exception):
                self._line_highlights.append((regex, 'exception'))
            else:
                self._line_highlights.append((regex, 'builtin'))
        for name in ['string', 'comment']:
            regex = re.compile(self.settings['regexes'][name])
            self._line_highlights.append((regex, name))
        # This will be used for removing old tags in highlight_line().
        # The same tag can be added multiple times, but there's no need
        # to remove it multiple times.
        self._line_highlight_tags = set()
        for regex, tag in self._line_highlights:
            self._line_highlight_tags.add(tag)

        self._multiline_string_regex = re.compile(
            self.settings['regexes']['multiline-string'], flags=re.DOTALL)

        indent = self.settings['editing'].getint('indent')
        if indent == 0:
            self._indentprefix = '\t'
        else:
            self._indentprefix = ' ' * indent

        self.bind('<Key>', self._on_key)
        self.bind('<Control-a>', self._on_ctrl_a)
        self.bind('<BackSpace>', self._on_backspace)
        for key in ('<parenright>', '<bracketright>', '<braceright>'):
            self.bind(key, self._on_closing_brace)
        self.bind('<Tab>', lambda event: self._on_tab(False))
        if self.tk.call('tk', 'windowingsystem') == 'x11':
            self.bind('<ISO_Left_Tab>', lambda event: self._on_tab(True))
        else:
            self.bind('<Shift-Tab>', lambda event: self._on_tab(True))
        self.bind('<Button-1>', self._on_click)

    def _on_ctrl_a(self, event):
        """Select all and return 'break' to stop the event handling."""
        self.tag_add('sel', '0.0', 'end')
        return 'break'     # don't run _on_key

    def _on_backspace(self, event):
        """Dedent and return 'break' if possible, if not call _on_key()."""
        if self._autodedent():
            return 'break'
        self._on_key(event)
        return None

    def _on_closing_brace(self, event):
        """Like _autodedent(), but ignore event and return None."""
        self._autodedent()

    def _on_tab(self, shifted):
        """Indent if shifted, dedent otherwise."""
        if shifted:
            action = self.dedent
        else:
            action = self.indent
        try:
            sel_start, sel_end = self.tag_ranges('sel')
        except ValueError:
            # nothing is selected
            lineno = int(self.index('insert').split('.')[0])
            action(lineno)
        else:
            # something is selected
            first_lineno = int(str(sel_start).split('.')[0])
            last_lineno = int(str(sel_end).split('.')[0])
            for lineno in range(first_lineno, last_lineno + 1):
                action(lineno)
        # indenting: don't insert the default tab
        # dedenting: don't move focus out of this widget
        return 'break'

    def _on_key(self, event):
        # The character is not inserted yet when this runs, so we use
        # after_idle to wait until the event is processed.
        if event.keysym == 'Return':
            # This is here because if we return 'break' from something
            # connected to '<Return>' it's impossible to actually type a
            # newline by pressing Return, but we don't really need to
            # run self.highlight_line().
            self.after_idle(self._autoindent)
            self.after_idle(self._strip_whitespace)
            self.after_idle(self.highlight_multiline)
        else:
            self.after_idle(self.highlight_line)
        self.after_idle(self.editor.update_statusbar)

    def _on_click(self, event):
        self.after_idle(self.editor.update_statusbar)

    def indent(self, lineno):
        """Indent by one level."""
        self.insert('%d.0' % lineno, self._indentprefix)
        self.editor.update_statusbar()

    def dedent(self, lineno):
        """Unindent by one level if possible."""
        start = '%d.0' % lineno
        end = '%d.%d' % (lineno, len(self._indentprefix))
        if self.get(start, end) == self._indentprefix:
            self.delete(start, end)
            self.editor.update_statusbar()

    def _autoindent(self):
        """Indent the current line automatically if needed."""
        lineno = int(self.index('insert').split('.')[0])
        prevline = self.get('%d.0-1l' % lineno, '%d.0' % lineno)
        # we can't run self._strip_whitespace() first because then we
        # wouldn't know if we are already in a block or not, so we just
        # .rstrip() here instead
        if prevline.rstrip().endswith((':', '(', '[', '{')):
            # start of a new block
            self.indent(lineno)
        # a block continues
        while prevline.startswith(self._indentprefix):
            self.indent(lineno)
            prevline = prevline[len(self._indentprefix):]

    def _autodedent(self):
        """Dedent the current line automatically if needed."""
        lineno = int(self.index('insert').split('.')[0])
        beforethis = self.get('%d.0' % lineno, 'insert')
        if beforethis.isspace():
            self.dedent(lineno)
            return True
        return False

    def _strip_whitespace(self):
        """Strip trailing whitespace from line before cursor."""
        lineno = int(self.index('insert').split('.')[0])
        start = '%d.0-1l' % lineno
        end = '%d.0-1c' % lineno
        old = self.get(start, end)
        new = old.rstrip()
        if old != new:
            self.delete('%d.%d' % (lineno-1, len(new)), end)
            # There's no need to update the statusbar because the current
            # line is never changed.

    def highlight_line(self, lineno=None):
        """Do all one-line highlighting needed."""
        # This must be fast because this is ran on (almost) every
        # keypress by _on_key().
        if lineno is None:
            # use cursor's line number
            lineno = int(self.index('insert').split('.')[0])
        line_start = '%d.0' % lineno
        line_end = '%d.0+1l' % lineno
        text = self.get(line_start, line_end).rstrip('\n')
        for tag in self._line_highlight_tags:
            self.tag_remove(tag, line_start, line_end)
        for regex, tag in self._line_highlights:
            for match in regex.finditer(text):
                start = '{}.0+{}c'.format(lineno, match.start())
                end = '{}.0+{}c'.format(lineno, match.end())
                self.tag_add(tag, start, end)

    def highlight_multiline(self):
        """Do all multiline highlighting needed.

        Currently only multiline strings need this.
        """
        text = self.get('0.0', 'end-1c')
        self.tag_remove('multiline-string', '0.0', 'end-1c')
        for match in self._multiline_string_regex.finditer(text):
            start, end = map('0.0+{}c'.format, match.span())
            self.tag_add('multiline-string', start, end)

    def highlight_all(self):
        """Highlight everything.

        This call highlight_multiline() once and highlight_line() with
        all possible line numbers.
        """
        linecount = int(self.index('end-1c').split('.')[0])
        for lineno in range(1, linecount + 1):
            self.highlight_line(lineno)
        self.highlight_multiline()
