"""The big text widget in the middle of the editor."""

import functools
import tkinter as tk

from porcupine import utils
from porcupine.settings import config, color_themes, InvalidValue


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


class HandyText(tk.Text):
    """Like ``tkinter.Text``, but with some handy features.

    All arguments are passed to ``tkinter.Text``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursorpos = (1, 0)

        #: This :class:`porcupine.utils.CallbackHook` will be ran when
        #: the user moves the cursor. It will be ran with the line and
        #: column numbers as arguments, where 1 is the first line and 0
        #: is the first column.
        self.cursor_move_hook = utils.CallbackHook(__name__)

        #: This :class:`porcupine.utils.CallbackHook` will be ran with
        #: no arguments when the user changes the content of the widget
        #: in any way or methods like ``insert()`` or ``delete()`` are
        #: used. Use this instead of binding ``<<Modified>>``.
        self.modified_hook = utils.CallbackHook(__name__)

        def cursor_move(event):
            self.after_idle(self.cursor_has_moved)

        for keysym in [
                '<Button-1>', '<Key>', '<<Undo>>', '<<Redo>>',
                '<<Cut>>', '<<Copy>>', '<<Paste>>', '<<Selection>>']:
            self.bind(keysym, cursor_move, add=True)
        self._modified_id = self.bind('<<Modified>>', self._do_modified)

    def _do_modified(self, event):
        # this runs recursively if we don't unbind
        self.unbind('<<Modified>>', self._modified_id)
        self.edit_modified(False)
        self._modified_id = self.bind('<<Modified>>', self._do_modified)
        self.modified_hook.run()
        self.cursor_has_moved()

    def cursor_has_moved(self):
        """Call this when the cursor may have moved.

        This does nothing if the cursor hasn't actually moved, so you
        don't need to worry about calling this too often. You may need
        to use ``after_idle`` if you are calling this from an event
        handler::

            def the_bind_callback(event):
                ...
                handytext.after_idle(handytext.cursor_has_moved)
        """
        line, column = map(int, self.index('insert').split('.'))
        if (line, column) != self._cursorpos:
            self._cursorpos = (line, column)
            self.cursor_move_hook.run(line, column)

    # setting a mark moves the cursor if the mark is 'insert'
    def mark_set(self, *args, **kwargs):
        super().mark_set(*args, **kwargs)
        self.cursor_has_moved()

    def iter_chunks(self):
        """Iterate over the content as 100-line chunks.

        This does not break lines in the middle.
        """
        start = 1
        while True:
            end = start + 100
            if self.index('%d.0' % end) == self.index('end'):
                yield self.get('%d.0' % start, 'end - 1 char')
                break

            yield self.get('%d.0' % start, '%d.0' % end)
            start = end


# this can be used for implementing other themed things too, e.g. the
# line number plugin
class ThemedText(HandyText):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config.connect('Editing', 'color_theme', self._set_theme, run_now=True)

    # tkinter seems to call this automatically
    def destroy(self):
        config.disconnect('Editing', 'color_theme', self._set_theme)
        super().destroy()

    def _set_theme(self, name):
        theme = color_themes[name]
        self['fg'] = theme['foreground']
        self['bg'] = theme['background']
        self['insertbackground'] = theme['foreground']  # cursor color
        self['selectforeground'] = theme['selectforeground']
        self['selectbackground'] = theme['selectbackground']


# TODO: turn indent/strip stuff into plugin(s)?
class MainText(ThemedText):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.complete_hook = utils.CallbackHook(__name__)

        partial = functools.partial     # pep8 line length
        self.bind('<BackSpace>', partial(self._on_delete, False))
        self.bind('<Control-BackSpace>', partial(self._on_delete, True))
        self.bind('<Control-Delete>', partial(self._on_delete, True))
        self.bind('<Shift-Control-Delete>',
                  partial(self._on_delete, True, shifted=True))
        self.bind('<Shift-Control-BackSpace>',
                  partial(self._on_delete, True, shifted=True))
        self.bind('<Return>', self._on_return)
        self.bind('<parenright>', self._on_closing_brace, add=True)
        self.bind('<bracketright>', self._on_closing_brace, add=True)
        self.bind('<braceright>', self._on_closing_brace, add=True)
        self.bind('<Control-z>', self.undo)
        self.bind('<Control-y>', self.redo)
        self.bind('<Control-x>', self.cut)
        self.bind('<Control-c>', self.copy)
        self.bind('<Control-v>', self.paste)
        self.bind('<Control-a>', self.select_all)
        self.bind('<Tab>', lambda event: self._on_tab(False))
        if self.tk.call('tk', 'windowingsystem') == 'x11':
            # even though the event keysym says Left, holding down right
            # shift and pressing tab also runs this event... 0_o
            self.bind('<ISO_Left_Tab>', lambda event: self._on_tab(True))
        else:
            self.bind('<Shift-Tab>', lambda event: self._on_tab(True))

        self.bind('<Control-plus>', lambda event: self.on_wheel('up'))
        self.bind('<Control-minus>', lambda event: self.on_wheel('down'))
        self.bind('<Control-0>', lambda event: self.on_wheel('reset'))
        utils.bind_mouse_wheel(self, self.on_wheel, prefixes='Control-')

        config.connect('Editing', 'undo', self._set_undo, run_now=True)

    def destroy(self):
        config.disconnect('Editing', 'undo', self._set_undo)
        super().destroy()

    def _set_undo(self, undo):
        self['undo'] = undo

    def on_wheel(self, direction):
        if direction == 'reset':
            config.reset(('Font', 'size'))
            return
        try:
            config['Font', 'size'] += (1 if direction == 'up' else -1)
        except InvalidValue:
            pass

    def _on_delete(self, control_down, event, shifted=False):
        """This runs when the user presses backspace or delete."""
        if not self.tag_ranges('sel'):
            # nothing is selected, we can do non-default stuff
            if control_down and shifted:
                # plan A: delete until end or beginning of line
                # plan B: delete a newline character if there's nothing
                #         to delete with plan A
                if event.keysym == 'Delete':
                    plan_a = ('insert', 'insert lineend')
                    plan_b = ('insert', 'insert + 1 char')
                else:
                    plan_a = ('insert linestart', 'insert')
                    plan_b = ('insert - 1 char', 'insert')

                if self.index(plan_a[0]) == self.index(plan_a[1]):
                    # nothing can be deleted with plan a
                    self.delete(*plan_b)
                else:
                    self.delete(*plan_a)
                return 'break'

            if event.keysym == 'BackSpace':
                lineno = int(self.index('insert').split('.')[0])
                before_cursor = self.get('%d.0' % lineno, 'insert')
                if before_cursor and before_cursor.isspace():
                    self.dedent(lineno)
                    return 'break'

                if control_down:
                    # delete previous word
                    end = self.index('insert')
                    self.event_generate('<<PrevWord>>')
                    self.delete('insert', end)
                    return 'break'

            if event.keysym == 'Delete' and control_down:
                # delete next word
                old_cursor_pos = self.index('insert')
                self.event_generate('<<NextWord>>')
                self.delete(old_cursor_pos, 'insert')

        self.after_idle(self.cursor_has_moved)
        return None

    def _on_return(self, event):
        """Schedule automatic indent and whitespace stripping."""
        # the whitespace must be stripped after autoindenting,
        # see _autoindent()
        self.after_idle(self._autoindent)
        self.after_idle(self._rstrip_prev_line)
        self.after_idle(self.cursor_has_moved)

    def _on_closing_brace(self, event):
        """Dedent automatically."""
        lineno = int(self.index('insert').split('.')[0])
        beforethis = self.get('%d.0' % lineno, 'insert')
        if beforethis.isspace():
            self.dedent(lineno)
        self.after_idle(self.cursor_has_moved)

    def _on_tab(self, shifted):
        """Indent, dedent or autocomplete."""
        if shifted:
            complete_arg = 'previous'
            indenter = self.dedent
        else:
            complete_arg = 'next'
            indenter = self.indent

        try:
            sel_start, sel_end = map(str, self.tag_ranges('sel'))
        except ValueError:
            # no text is selected
            lineno = int(self.index('insert').split('.')[0])
            before_cursor = self.get('%d.0' % lineno, 'insert')
            if before_cursor.isspace() or not before_cursor:
                indenter(lineno)
            else:
                self.complete_hook.run(complete_arg)
        else:
            # something selected, indent/dedent block
            first_lineno = int(sel_start.split('.')[0])
            last_lineno = int(sel_end.split('.')[0])
            for lineno in range(first_lineno, last_lineno+1):
                indenter(lineno)
                self.rstrip(lineno)

        # indenting and autocomplete: don't insert the default tab
        # dedenting: don't move focus out of this widget
        return 'break'

    def indent(self, lineno):
        """Indent by one level.

        Return the resulting number of spaces in the beginning of
        the line.
        """
        line = self.get('%d.0' % lineno, '%d.0 lineend' % lineno)
        spaces = spacecount(line)
        indent = config['Editing', 'indent']

        # make the indent consistent, for example, add 1 space if indent
        # is 4 and there are 7 spaces
        spaces2add = indent - (spaces % indent)
        self.insert('%d.0' % lineno, ' ' * spaces2add)
        self.cursor_has_moved()
        return spaces + spaces2add

    def dedent(self, lineno):
        """Unindent by one level if possible.

        Return the resulting number of spaces in the beginning of
        the line.
        """
        line = self.get('%d.0' % lineno, '%d.0 lineend' % lineno)
        spaces = spacecount(line)
        if spaces == 0:
            return 0

        indent = config['Editing', 'indent']
        howmany2del = spaces % indent
        if howmany2del == 0:
            howmany2del = indent
        self.delete('%d.0' % lineno, '%d.%d' % (lineno, howmany2del))
        self.cursor_has_moved()
        return spaces - howmany2del

    def _autoindent(self):
        """Indent or dedent the current line automatically if needed."""
        lineno = int(self.index('insert').split('.')[0])
        prevline = self.get('%d.0 - 1 line' % lineno, '%d.0' % lineno)
        self.insert('insert', spacecount(prevline) * ' ')

        # we can't strip trailing whitespace before this because then
        # pressing enter twice would get rid of all indentation
        prevline = prevline.strip()
        if prevline.endswith((':', '(', '[', '{')):
            # start of a new block
            self.indent(lineno)
        elif (prevline in {'return', 'break', 'pass'}
              or prevline.startswith(('return ', 'raise '))):
            # must be end of a block
            self.dedent(lineno)

    def rstrip(self, lineno):
        """Strip trailing whitespace at the end of a line."""
        line_end = '%d.0 lineend' % lineno
        line = self.get('%d.0' % lineno, line_end)
        spaces = spacecount(line[::-1])
        if spaces == 0:
            return

        deleting_start = '%s - %d chars' % (line_end, spaces)
        self.delete(deleting_start, line_end)

    def _rstrip_prev_line(self):
        """Strip whitespace after end of previous line."""
        lineno = int(self.index('insert').split('.')[0])
        self.rstrip(lineno-1)

    def undo(self, event=None):
        try:
            self.edit_undo()
        except tk.TclError:     # nothing to undo
            return
        self.cursor_has_moved()
        return 'break'

    def redo(self, event=None):
        try:
            self.edit_redo()
        except tk.TclError:     # nothing to redo
            return
        self.cursor_has_moved()
        return 'break'

    def cut(self, event=None):
        self.event_generate('<<Cut>>')
        return 'break'

    def copy(self, event=None):
        self.event_generate('<<Copy>>')
        return 'break'

    def paste(self, event=None):
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

        return 'break'

    def select_all(self, event=None):
        self.tag_add('sel', '1.0', 'end - 1 char')
        return 'break'
