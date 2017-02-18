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


def spacecount(string):
    """Count how many space characters the string starts with.

    >>> spacecount('  123')
    2
    >>> spacecount('  \n')
    2
    """
    result = 0
    for char in string:
        # we don't use isspace() here because '\n'.isspace() is True
        if char != ' ':
            return result
        result += 1


class EditorText(tk.Text):

    def __init__(self, master, settings, **kwargs):
        self._settings = settings
        super().__init__(master, **kwargs)

        # These will contain callback functions that are ran after the
        # text in the textview is updated. on_other_insert callbacks are
        # ran when text is inserted to the textwidget without running
        # other callbacks, e.g. by pasting.
        self.on_cursor_move = []        # callback(lineno, column)
        self.on_linecount_changed = []  # callback(linecount)
        self.on_other_insert = []       # callback()
        self._cursorpos = (1, 0)
        self._linecount = 1

        def cursor_move(event):
            self.after_idle(self.do_cursor_move)

        self.bind('<Button-1>', cursor_move)
        self.bind('<Key>', cursor_move)
        self.bind('<Control-a>', self._on_ctrl_a)
        self.bind('<BackSpace>', self._on_backspace)
        self.bind('<Delete>', self._on_delete)
        self.bind('<Return>', self._on_return)
        self.bind('<parenright>', self._on_closing_brace)
        self.bind('<bracketright>', self._on_closing_brace)
        self.bind('<braceright>', self._on_closing_brace)
        self.bind('<Tab>', lambda event: self._on_tab(False))
        if self.tk.call('tk', 'windowingsystem') == 'x11':
            # even though the event keysym says Left, holding down right
            # shift and pressing tab also runs this event... 0_o
            self.bind('<ISO_Left_Tab>', lambda event: self._on_tab(True))
        else:
            self.bind('<Shift-Tab>', lambda event: self._on_tab(True))

    def do_cursor_move(self):
        line, column = map(int, self.index('insert').split('.'))
        if self._cursorpos != (line, column):
            self._cursorpos = (line, column)
            for callback in self.on_cursor_move:
                callback(line, column)

    def do_linecount_changed(self):
        linecount = int(self.index('end-1c').split('.')[0])
        if self._linecount != linecount:
            self._linecount = linecount
            for callback in self.on_linecount_changed:
                callback(linecount)

    def do_other_insert(self):
        for callback in self.on_other_insert:
            callback()

    def _on_backspace(self, event):
        if not self.tag_ranges('sel'):
            # nothing is selected, we can do non-default stuff
            prevchar = self.get('insert-1c', 'insert')
            if prevchar:
                # not beginning of file
                lineno = int(self.index('insert').split('.')[0])
                before_cursor = self.get('%d.0' % lineno,
                                         '%d.0+1l-1c' % lineno)
                if before_cursor.isspace():
                    self.dedent(lineno)
                    return 'break'

        self.after_idle(self.do_linecount_changed)
        self.after_idle(self.do_cursor_move)
        return None

    def _on_ctrl_a(self, event):
        """Select all."""
        self.tag_add('sel', '0.0', 'end-1c')
        return 'break'     # don't run _on_key or move cursor

    def _on_delete(self, event):
        nextchar = self.get('insert', 'insert+1c')
        if nextchar:
            # not end of file
            self.after_idle(self.do_linecount_changed)
            self.after_idle(self.do_cursor_move)

    def _on_return(self, event):
        """Schedule automatic indent and whitespace stripping."""
        # the whitespace must be stripped after autoindenting,
        # see _autoindent()
        self.after_idle(self._autoindent)
        self.after_idle(self._strip_whitespace)
        self.after_idle(self.do_cursor_move)
        self.after_idle(self.do_linecount_changed)

    def _on_closing_brace(self, event):
        """Dedent automatically."""
        lineno = int(self.index('insert').split('.')[0])
        beforethis = self.get('%d.0' % lineno, 'insert')
        if beforethis.isspace():
            self.dedent(lineno)
            return True
        return False

    def _on_tab(self, shifted):
        if shifted:
            action = self.dedent
        else:
            action = self.indent

        try:
            sel_start, sel_end = map(str, self.tag_ranges('sel'))
        except ValueError:
            # no text is selected
            lineno = int(self.index('insert').split('.')[0])
            before_cursor = self.get('%d.0' % lineno, 'insert')
            if before_cursor.isspace() or not before_cursor:
                action(lineno)
            else:
                print("complete", "previous" if shifted else "next")
        else:
            # something selected, indent/dedent block
            first_lineno = int(sel_start.split('.')[0])
            last_lineno = int(sel_end.split('.')[0])
            for lineno in range(first_lineno, last_lineno+1):
                action(lineno)

        # indenting and autocomplete: don't insert the default tab
        # dedenting: don't move focus out of this widget
        return 'break'

    def indent(self, lineno):
        """Indent by one level.

        Return the resulting number of spaces in the beginning of
        the line.
        """
        line = self.get('%d.0' % lineno, '%d.0+1l' % lineno)
        spaces = spacecount(line)

        # make the indent consistent, for example, add 1 space
        # if self._settings['indent'] is 4 and there are 7 spaces
        indent = self._settings['indent']
        spaces2add = indent - (spaces % indent)
        self.insert('%d.0' % lineno, ' ' * spaces2add)
        self.do_cursor_move()
        return spaces + spaces2add

    def dedent(self, lineno):
        """Unindent by one level if possible.

        Return the resulting number of spaces in the beginning of
        the line.
        """
        line = self.get('%d.0' % lineno, '%d.0+1l' % lineno)
        spaces = spacecount(line)
        if spaces == 0:
            return 0
        howmany2del = spaces % self._settings['indent']
        if howmany2del == 0:
            howmany2del = self._settings['indent']
        self.delete('%d.0' % lineno, '%d.%d' % (lineno, howmany2del))
        self.do_cursor_move()
        return spaces - howmany2del

    def _autoindent(self):
        """Indent the current line automatically as needed."""
        lineno = int(self.index('insert').split('.')[0])
        prevline = self.get('%d.0-1l' % lineno, '%d.0' % lineno)
        # we can't strip trailing whitespace before this because then
        # pressing enter twice would get rid of all indentation
        if prevline.rstrip().endswith((':', '(', '[', '{')):
            # start of a new block
            self.indent(lineno)
        # a block continues
        self.insert('insert', spacecount(prevline) * ' ')

    def _strip_whitespace(self):
        """Strip whitespace after end of previous line."""
        lineno = self.index('insert').split('.')[0]
        end = '%s.0+1l-1c' % lineno
        if self.get('insert', end).isspace():
            self.delete('insert', end)

    def undo(self):
        try:
            self.edit_undo()
        except tk.TclError:     # nothing to undo
            return
        self.do_cursor_move()
        self.do_linecount_changed()

    def redo(self):
        try:
            self.edit_redo()
        except tk.TclError:     # nothing to redo
            return
        self.do_cursor_move()
        self.do_linecount_changed()
