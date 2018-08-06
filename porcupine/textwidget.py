import functools
import tkinter as tk
import tkinter.font as tkfont

import pygments.styles

from porcupine import settings, utils


class HandyText(tk.Text):
    """Like ``tkinter.Text``, but with some handy features.

    All arguments are passed to ``tkinter.Text``.

    .. virtualevent:: ContentChanged

        This event is generated when the text in the widget is modified
        in any way, and it's implemented with ``<<Modified>>``. Unlike
        ``<<Modified>>``, this event is simply generated every time the
        content changes, and there's no need to unset a flag like
        ``textwidget.edit_modified(False)`` or anything like that.

        .. note::
            Don't use ``<<Modified>>`` or ``edit_modified()`` with
            HandyText. They would conflict with the
            ``<<ContentChanged>>`` implementation, and
            ``<<ContentChanged>>`` is easier to use in general.

    .. virtualevent:: CursorMoved

        This event is generated every time the user moves the cursor or
        it's moved with a method of the text widget. Use
        ``textwidget.index('insert')`` to find the current cursor
        position.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def cursor_move(event):
            self.after_idle(self.cursor_has_moved)

        self._cursorpos = '1.0'
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
        self.event_generate('<<ContentChanged>>')
        self.cursor_has_moved()

    def cursor_has_moved(self):
        """
        Call this when the cursor may have moved and the text widget
        hasn't noticed it for some reason.

        This does nothing if the cursor hasn't actually moved, so you
        don't need to worry about calling this too often.

        You may need to use ``after_idle`` if you are calling this from
        an event handler::

            def the_bind_callback(event):
                ...
                handytext.after_idle(handytext.cursor_has_moved)

        Event handlers are ran before anything happens, and this way
        ``handytext.cursor_has_moved()`` runs *after* the event has been
        processed and the cursor has actually moved.
        """
        if self.index('insert') != self._cursorpos:
            self._cursorpos = self.index('insert')
            self.event_generate('<<CursorMoved>>')

    # this is not perfect, but the langserver branch has a much better way to
    # do this
    @functools.wraps(tk.Text.insert)
    def insert(self, *args, **kwargs):
        super().insert(*args, **kwargs)
        self.cursor_has_moved()

    @functools.wraps(tk.Text.delete)
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.cursor_has_moved()

    # setting a mark moves the cursor if the mark is 'insert'
    @functools.wraps(tk.Text.mark_set)
    def mark_set(self, *args, **kwargs):
        super().mark_set(*args, **kwargs)
        self.cursor_has_moved()

    def iter_chunks(self, n=100):
        r"""Iterate over the content as chunks of *n* lines.

        Each yielded line ends with a ``\n`` character. Lines are not
        broken down the middle, and ``''`` is never yielded.

        Note that the last chunk is less than *n* lines long unless the
        total number of lines is divisible by *n*.
        """
        start = 1     # this is not a mistake, line numbers start at 1
        while True:
            end = start + n
            if self.index('%d.0' % end) == self.index('end'):
                # '%d.0' % start can be 'end - 1 char' in a corner
                # case, let's not yield an empty string
                last_chunk = self.get('%d.0' % start, 'end - 1 char')
                if last_chunk:
                    yield last_chunk
                break

            yield self.get('%d.0' % start, '%d.0' % end)
            start = end

    def iter_lines(self):
        r"""Iterate over the content as lines.

        The trailing ``\n`` characters of each line are included.
        """
        for chunk in self.iter_chunks():
            yield from chunk.splitlines(keepends=True)


# this can be used for implementing other themed things too, e.g. the
# line number plugin
class ThemedText(HandyText):
    """A :class:`.HandyText` subclass that uses the Pygments style's colors.

    You can use this class just like :class:`.HandyText`, it takes care
    of switching the colors by itself. This is useful for things like
    :source:`porcupine/plugins/linenumbers.py`.

    .. seealso::
        Syntax highlighting is implemented with Pygments in
        :source:`porcupine/plugins/highlight.py`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        settings.get_section('General').connect(
            'pygments_style', self._set_style, run_now=True)

        def on_destroy(event):
            settings.get_section('General').disconnect(
                'pygments_style', self._set_style)

        self.bind('<Destroy>', on_destroy, add=True)

    def _set_style(self, name):
        style = pygments.styles.get_style_by_name(name)
        bg = style.background_color

        # yes, style.default_style can be '#rrggbb', '' or nonexistent
        # this is undocumented
        #
        #   >>> from pygments.styles import *
        #   >>> [getattr(get_style_by_name(name), 'default_style', '???')
        #   ...  for name in get_all_styles()]
        #   ['', '', '', '', '', '', '???', '???', '', '', '', '',
        #    '???', '???', '', '#cccccc', '', '', '???', '', '', '', '',
        #    '#222222', '', '', '', '???', '']
        fg = getattr(style, 'default_style', '') or utils.invert_color(bg)

        self['fg'] = fg
        self['bg'] = bg
        self['insertbackground'] = fg  # cursor color

        # this is actually not too bad :D
        self['selectforeground'] = bg
        self['selectbackground'] = fg


class MainText(ThemedText):
    """Don't use this. It may be changed later."""

    # the filetype is needed for setting the tab width and indenting
    def __init__(self, parent, filetype, **kwargs):
        super().__init__(parent, **kwargs)
        self.set_filetype(filetype)

        # FIXME: lots of things have been turned into plugins, but
        # there's still wayyyy too much stuff in here...
        partial = functools.partial     # pep8 line length
        self.bind('<BackSpace>', partial(self._on_delete, False))
        self.bind('<Control-BackSpace>', partial(self._on_delete, True))
        self.bind('<Control-Delete>', partial(self._on_delete, True))
        self.bind('<Shift-Control-Delete>',
                  partial(self._on_delete, True, shifted=True))
        self.bind('<Shift-Control-BackSpace>',
                  partial(self._on_delete, True, shifted=True))
        self.bind('<Return>', (lambda event: self.cursor_has_moved()))
        self.bind('<parenright>', self._on_closing_brace, add=True)
        self.bind('<bracketright>', self._on_closing_brace, add=True)
        self.bind('<braceright>', self._on_closing_brace, add=True)

        # most other things work by default, but these don't
        self.bind('<Control-v>', self._paste)
        self.bind('<Control-y>', self._redo)
        self.bind('<Control-a>', self._select_all)

        utils.bind_mouse_wheel(self, self._on_ctrl_wheel, prefixes='Control-')

    # TODO: the run plugin contains similar code, maybe reuse it somehow?
    def _on_ctrl_wheel(self, direction):
        config = settings.get_section('General')
        if direction == 'reset':
            config.reset('font_size')
            return

        try:
            config['font_size'] += (1 if direction == 'up' else -1)
        except settings.InvalidValue:
            pass

    def set_filetype(self, filetype):
        self._filetype = filetype

        # from the text(3tk) man page: "To achieve a different standard
        # spacing, for example every 4 characters, simply configure the
        # widget with “-tabs "[expr {4 * [font measure $font 0]}] left"
        # -tabstyle wordprocessor”."
        #
        # my version is kind of minimal compared to that example, but it
        # seems to work :)
        font = tkfont.Font(name=self['font'], exists=True)
        self['tabs'] = str(font.measure(' ' * filetype.indent_size))

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
                    self.dedent('insert')
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

    def _on_closing_brace(self, event):
        """Dedent automatically."""
        self.dedent('insert')
        self.after_idle(self.cursor_has_moved)

    def indent(self, location):
        """Insert indentation character(s) at the given location."""
        if not self._filetype.tabs2spaces:
            self.insert(location, '\t')
            return

        # we can't just add ' '*self._filetype.indent_size, for example,
        # if indent_size is 4 and there are 7 charaters we add 1 space
        spaces = self._filetype.indent_size    # pep-8 line length
        how_many_chars = int(self.index(location).split('.')[1])
        spaces2add = spaces - (how_many_chars % spaces)
        self.insert(location, ' ' * spaces2add)
        self.cursor_has_moved()

    def dedent(self, location):
        """Remove indentation character(s) if possible.

        This method tries to remove spaces intelligently so that
        everything's lined up evenly based on the indentation settings.
        This method is useful for dedenting whole lines (with location
        set to beginning of the line) or deleting whitespace in the
        middle of a line.

        This returns True if something was done, and False otherwise.
        """
        if not self._filetype.tabs2spaces:
            one_back = '%s - 1 char' % location
            if self.get(one_back, location) == '\t':
                self.delete(one_back, location)
                return True
            return False

        lineno, column = map(int, self.index(location).split('.'))
        line = self.get('%s linestart' % location, '%s lineend' % location)

        if column == 0:
            start = 0
            end = self._filetype.indent_size
        else:
            start = column - (column % self._filetype.indent_size)
            if start == column:    # prefer deleting from left side
                start -= self._filetype.indent_size
            end = start + self._filetype.indent_size

        end = min(end, len(line))    # don't go past end of line
        if start == 0:
            # delete undersized indents
            whitespaces = len(line) - len(line.lstrip())
            end = min(whitespaces, end)

        if not line[start:end].isspace():   # ''.isspace() is False
            return False
        self.delete('%d.%d' % (lineno, start), '%d.%d' % (lineno, end))
        return True

    def _redo(self, event):
        self.event_generate('<<Redo>>')   # runs cursor_has_moved, see __init__
        return 'break'

    def _paste(self, event):
        self.event_generate('<<Paste>>')  # runs cursor_has_moved, see __init__

        # by default, selected text doesn't go away when pasting
        try:
            sel_start, sel_end = self.tag_ranges('sel')
        except ValueError:
            # nothing selected
            pass
        else:
            self.delete(sel_start, sel_end)

        return 'break'

    def _select_all(self, event):
        self.tag_add('sel', '1.0', 'end - 1 char')
        return 'break'
