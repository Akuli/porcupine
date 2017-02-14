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

import tkinter as tk

from . import highlight


class EditorText(tk.Text):

    def __init__(self, master, editor, **kwargs):
        self.editor = editor
        self.settings = settings = editor.settings
        fg = settings['colors']['foreground']

        super().__init__(
            master, foreground=fg, selectbackground=fg,
            insertbackground=fg,   # TODO: fix this
            background=settings['colors']['background'], undo=True,
            maxundo=settings['maxundo'],
            blockcursor=settings['blockcursor'], font=settings['font'],
            **kwargs)

        self.highlighter = highlight.SyntaxHighlighter(self, settings)

        indent = settings['indent']
        if indent == 0:
            self._indentprefix = '\t'
        else:
            self._indentprefix = ' ' * indent

        self.bind('<Key>', self._on_key)
        self.bind('<Control-a>', self._on_ctrl_a)
        self.bind('<BackSpace>', self._on_backspace)
        self.bind('<Delete>', self._on_delete)
        self.bind('<Return>', self._on_return)
        self.bind('<parenright>', self._on_closing_brace)
        self.bind('<bracketright>', self._on_closing_brace)
        self.bind('<braceright>', self._on_closing_brace)
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
        """Dedent if possible."""
        if self._autodedent():
            return 'break'
        self._on_key(event)
        self.after_idle(self.editor.linenumbers.do_update)
        return None

    def _on_delete(self, event):
        """Schedule a line number update."""
        self.after_idle(self.editor.linenumbers.do_update)
        self._on_key(event)

    def _on_return(self, event):
        # The character is not inserted yet when this runs, so we use
        # after_idle to wait until the event is processed.
        self.after_idle(self._autoindent)
        self.after_idle(self.strip_whitespace,
                        int(self.index('insert').split('.')[0]))
        self.after_idle(self.highlighter.highlight_multiline)
        self.after_idle(self.editor.linenumbers.do_update)
        self._on_key(event)

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
        self.after_idle(self.highlighter.highlight_line)
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

    def strip_whitespace(self, lineno):
        """Strip whitespace from end of a line."""
        start = '%d.0' % lineno
        end = '%d.0+1l-1c' % lineno
        old = self.get(start, end)
        new = old.rstrip()
        if old != new:
            self.delete('%d.%d' % (lineno, len(new)), end)
