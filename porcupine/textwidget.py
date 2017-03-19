"""The big text widget in the middle of the editor."""

from functools import partial   # not "import functools" to avoid long lines
import tkinter as tk

from porcupine.settings import config, color_themes


def spacecount(string):
    """Count how many spaces the string starts with.

    >>> spacecount('  123')
    2
    >>> spacecount('  \n')
    2
    """
    result = 0
    for char in string:
        if char == '\n' or not char.isspace():
            break
        result += 1
    return result


class EditorText(tk.Text):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # These will contain callback functions that are called with no
        # arguments after the text in the textview is updated.
        self.on_cursor_move = []
        self.on_modified = []
        self.on_complete_previous = []
        self.on_complete_next = []
        self._cursorpos = '1.0'

        def cursor_move(event):
            self.after_idle(self._do_cursor_move)

        self.bind('<<Modified>>', self._do_modified)
        self.bind('<Button-1>', cursor_move)
        self.bind('<Key>', cursor_move)
        self.bind('<Control-a>', self._on_ctrl_a)
        self.bind('<BackSpace>', partial(self._on_delete, False))
        self.bind('<Control-BackSpace>', partial(self._on_delete, True))
        self.bind('<Control-Delete>', partial(self._on_delete, True))
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

        config.connect('editing:undo', self._on_config_changed)
        config.connect('editing:color_theme', self._on_config_changed)
        self._on_config_changed('editing:undo')
        self._on_config_changed('editing:color_theme')

    def _on_config_changed(self, key, value=None):
        if value is None:
            # called from __init__
            value = config[key]

        if key == 'editing:undo':
            self['undo'] = value
        elif key == 'editing:color_theme':
            theme = color_themes[value]
            self['fg'] = theme['foreground']
            self['bg'] = theme['background']
            self['insertbackground'] = theme['foreground']  # cursor color
            self['selectforeground'] = theme['selectforeground']
            self['selectbackground'] = theme['selectbackground']

    def _do_modified(self, event):
        # this runs recursively if we don't unbind
        self.unbind('<<Modified>>')
        self.edit_modified(False)
        self.bind('<<Modified>>', self._do_modified)
        for callback in self.on_modified:
            callback()

    def _do_cursor_move(self):
        cursorpos = self.index('insert')
        if cursorpos != self._cursorpos:
            self._cursorpos = cursorpos
            for callback in self.on_cursor_move:
                callback()

    def _on_delete(self, control_down, event):
        """This runs when the user presses backspace or delete."""
        if not self.tag_ranges('sel'):
            # nothing is selected, we can do non-default stuff
            if event.keysym == 'BackSpace':
                lineno = int(self.index('insert').split('.')[0])
                before_cursor = self.get('%d.0' % lineno, 'insert')
                if before_cursor and before_cursor.isspace():
                    self.dedent(lineno)
                    return 'break'

                if control_down:
                    # delete previous word
                    old_cursor_pos = self.index('insert')
                    self.event_generate('<<PrevWord>>')
                    self.delete('insert', old_cursor_pos)
                    return 'break'

            if event.keysym == 'Delete' and control_down:
                # delete next word
                old_cursor_pos = self.index('insert')
                self.event_generate('<<NextWord>>')
                self.delete(old_cursor_pos, 'insert')

        self.after_idle(self._do_cursor_move)
        return None

    def _on_ctrl_a(self, event):
        """Select all."""
        self.tag_add('sel', '1.0', 'end-1c')
        return 'break'     # don't run _on_key or move cursor

    def _on_return(self, event):
        """Schedule automatic indent and whitespace stripping."""
        # the whitespace must be stripped after autoindenting,
        # see _autoindent()
        self.after_idle(self._autoindent)
        self.after_idle(self._strip_whitespace)
        self.after_idle(self._do_cursor_move)

    def _on_closing_brace(self, event):
        """Dedent automatically."""
        lineno = int(self.index('insert').split('.')[0])
        beforethis = self.get('%d.0' % lineno, 'insert')
        if beforethis.isspace():
            self.dedent(lineno)
        self.after_idle(self._do_cursor_move)

    def _on_tab(self, shifted):
        """Indent, dedent or autocomplete."""
        if shifted:
            indent_action = self.dedent
            complete_callbacks = self.on_complete_previous
        else:
            indent_action = self.indent
            complete_callbacks = self.on_complete_next

        try:
            sel_start, sel_end = map(str, self.tag_ranges('sel'))
        except ValueError:
            # no text is selected
            lineno = int(self.index('insert').split('.')[0])
            before_cursor = self.get('%d.0' % lineno, 'insert')
            if before_cursor.isspace() or not before_cursor:
                indent_action(lineno)
            else:
                for callback in complete_callbacks:
                    callback()
        else:
            # something selected, indent/dedent block
            first_lineno = int(sel_start.split('.')[0])
            last_lineno = int(sel_end.split('.')[0])
            for lineno in range(first_lineno, last_lineno+1):
                indent_action(lineno)

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
        indent = config['editing:indent']

        # make the indent consistent, for example, add 1 space if indent
        # is 4 and there are 7 spaces
        spaces2add = indent - (spaces % indent)
        self.insert('%d.0' % lineno, ' ' * spaces2add)
        self._do_cursor_move()
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

        indent = config['editing:indent']
        howmany2del = spaces % indent
        if howmany2del == 0:
            howmany2del = indent
        self.delete('%d.0' % lineno, '%d.%d' % (lineno, howmany2del))
        self._do_cursor_move()
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
        lineno = int(self.index('insert').split('.')[0])
        line = self.get('%d.0-1l' % lineno, '%d.0-1c' % lineno)

        spaces = spacecount(line[::-1])
        if spaces == 0:
            return

        start = '{}.0-1c-{}c'.format(lineno, spaces)
        end = '{}.0-1c'.format(lineno)
        self.delete(start, end)

    def undo(self):
        try:
            self.edit_undo()
        except tk.TclError:     # nothing to undo
            return
        self._do_cursor_move()
        return 'break'

    def redo(self):
        try:
            self.edit_redo()
        except tk.TclError:     # nothing to redo
            return
        self._do_cursor_move()
        return 'break'

    def cut(self):
        self.event_generate('<<Cut>>')
        self._do_cursor_move()

    def copy(self):
        self.event_generate('<<Copy>>')
        self._do_cursor_move()

    def paste(self):
        self.event_generate('<<Paste>>')

        # Without this, pasting while some text is selected is annoying
        # because the selected text doesn't go away :(
        try:
            sel_start, sel_end = self.tag_ranges('sel')
        except ValueError:
            # nothing selected
            pass
        else:
            self.delete(sel_start, sel_end)

        self._do_cursor_move()
