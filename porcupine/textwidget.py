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
        in any way. Unlike ``<<Modified>>``, this event is simply generated
        every time the content changes, and there's no need to unset a flag
        like ``textwidget.edit_modified(False)`` or anything like that.

        If you want to know what changed and how, use
        :func:`porcupine.utils.bind_with_data` and
        ``event.data_tuple(str, str, int, str)``. The first 2 values of the
        tuple are indexes in the text widget before the text change occurs, the
        3rd value is the number of characters that were between the indexes
        before deleting (including newlines) and the 4th value is the new text
        as a string. So, if the text widget contains ``'hello world'``, then
        this...
        ::

            # characters 0 to 5 on 1st line are the hello
            textwidget.replace('1.0', '1.5', 'toot')

        ...changes the ``'hello'`` to ``'toot'``, generating a
        ``<<ContentChanged>>`` event with ``data_tuple(str, str, int, str)``
        like this::

            ('1.0', '1.5', 5, 'toot')

        Note that is ``len('hello')``, not ``len('toot')``; it represents the
        length of the old text.

        Unlike you might think, the 5 is not redundant here. If the whole
        ``'toot world'`` is changed to ``''``...
        ::

            ('1.0', '1.10', 10, '')

        ...then ``'1.10'`` is no longer a valid index in the text widget
        because it contains 0 characters (and 0 is less than 10). In this case,
        checking only the ``0`` of ``1.0`` and the ``10`` of ``1.10`` could be
        used to calculate the 10, but that doesn't work right when changing a
        multiple lines.

    .. virtualevent:: CursorMoved

        This event is generated every time the user moves the cursor or
        it's moved with a method of the text widget. Use
        ``textwidget.index('insert')`` to find the current cursor
        position.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # cursor_cb is called whenever the cursor position may have changed,
        # and change_cb is called whenever the content of the text widget may
        # have changed
        change_cb_command = self.register(self._change_cb)
        cursor_cb_command = self.register(self._cursor_cb)

        # all widget stuff is implemented in python and in tcl as calls to a
        # tcl command named str(self), and replacing that with a custom command
        # is a very powerful way to do magic; for example, moving the cursor
        # with arrow keys calls the insert widget command :D
        actual_widget_command = str(self) + '_actual_widget'
        self.tk.call('rename', str(self), actual_widget_command)

        # this part is tcl because i couldn't get a python callback to work
        self.tk.eval('''
        proc %(fake_widget)s {args} {
            #puts $args

            # subcommand is e.g. insert, delete, replace, index, search, ...
            # see text(3tk) for all possible subcommands
            set subcommand [lindex $args 0]

            set cursor_may_have_moved 0

            # only these subcommands can change the text, but they can also
            # move the cursor by changing the text before the cursor
            if {$subcommand == "delete" ||
                    $subcommand == "insert" ||
                    $subcommand == "replace"} {
                set cursor_may_have_moved 1

                # this is like self._change_cb(*args) in python
                %(change_cb)s {*}$args
            }

            # it's important that this comes after the change cb stuff because
            # this way it's possible to get old_length in self._change_cb()...
            # however, it's also important that this is before the mark set
            # stuff because the documented way to access the new index in a
            # <<CursorMoved>> binding is getting it directly from the widget
            set result [%(actual_widget)s {*}$args]

            # only[*] 'textwidget mark set insert new_location' can change the
            # cursor position, because the cursor position is implemented as a
            # mark named "insert" and there are no other commands that move
            # marks
            #
            # [*] i lied, hehe >:D MUHAHAHA ... inserting text before the
            # cursor also changes it
            if {$subcommand == "mark" &&
                    [lindex $args 1] == "set" &&
                    [lindex $args 2] == "insert"} {
                set cursor_may_have_moved 1
            }

            if {$cursor_may_have_moved} {
                %(cursor_cb)s
            }

            return $result
        }
        ''' % {
            'fake_widget': str(self),
            'actual_widget': actual_widget_command,
            'change_cb': change_cb_command,
            'cursor_cb': cursor_cb_command,
        })

        # see _cursor_cb
        self._old_cursor_pos = self.index('insert')

    def _change_cb(self, subcommand, *args):
        # contains (start, end, old_length, new_text) tuples
        changes = []

        # search for 'pathName delete' in text(3tk)... it's a wall of text,
        # and this thing has to implement every detail of that wall
        if subcommand == 'delete':
            # "All indices are first checked for validity before any deletions
            # are made." they are already validated, but this doesn't hurt
            # imo... but note that rest of this code assumes that this is done!
            # not everything works in corner cases without this
            args = [self.index(arg) for arg in args]

            # tk has a funny abstraction of an invisible newline character at
            # the end of file, it's always there but nothing else uses it, so
            # let's ignore it
            for index, old_arg in enumerate(args):
                if old_arg == self.index('end'):
                    args[index] = self.index('end - 1 char')

            # "If index2 is not specified then the single character at index1
            # is deleted." and later: "If more indices are given, multiple
            # ranges of text will be deleted." but no mention about combining
            # these features, this works like the text widget actually behaves
            if len(args) % 2 == 1:
                args.append(self.index('%s + 1 char' % args[-1]))
            assert len(args) % 2 == 0
            pairs = zip(args[0::2], args[1::2])   # an iterator, not a list yet

            # "If index2 does not specify a position later in the text than
            # index1 then no characters are deleted."
            # note that this also converts pairs to a list
            pairs = [(start, end) for (start, end) in pairs
                     if self.compare(start, '<', end)]

            # "They [index pairs, aka ranges] are sorted [...]."
            def sort_by_range_beginnings(self, pair):
                (start1, _), (start2, _) = pair
                if self.compare(start1, '>', start2):
                    return 1
                if self.compare(start1, '<', start2):
                    return -1
                return 0

            pairs.sort(key=functools.cmp_to_key(sort_by_range_beginnings))

            # "If multiple ranges with the same start index are given, then the
            # longest range is used. If overlapping ranges are given, then they
            # will be merged into spans that do not cause deletion of text
            # outside the given ranges due to text shifted during deletion."
            def merge_index_ranges(start1, end1, start2, end2):
                start = start1 if self.compare(start1, '<', start2) else start2
                end = end1 if self.compare(end1, '>', end2) else end2
                return (start, end)

            # loop through pairs of pairs
            for i in range(len(pairs)-2, -1, -1):
                (start1, end1), (start2, end2) = pairs[i:i+2]
                if self.compare(end1, '<=', start2):
                    # they overlap
                    new_pair = merge_index_ranges(start1, end1, start2, start2)
                    pairs[i:i+2] = [new_pair]

            # "[...] and the text is removed from the last range to the first
            # range so deleted text does not cause an undesired index shifting
            # side-effects."
            for start, end in reversed(pairs):
                changes.append((start, end, len(self.get(start, end)), ''))

        # the man page's inserting section is also kind of a wall of
        # text, but not as bad as the delete
        elif subcommand == 'insert':
            index, *other_args = args
            index = self.index(index)

            # "If index refers to the end of the text (the character after the
            # last newline) then the new text is inserted just before the last
            # newline instead."
            if index == self.index('end'):
                index = self.index('end - 1 char')

            # we don't care about the tagList arguments to insert, but we need
            # to handle the other arguments nicely anyway: "If multiple
            # chars-tagList argument pairs are present, they produce the same
            # effect as if a separate pathName insert widget command had been
            # issued for each pair, in order. The last tagList argument may be
            # omitted." i'm not sure what "in order" means here, but i tried
            # it, and 'textwidget.insert('1.0', 'asd', [], 'toot', [])' inserts
            # 'asdtoot', not 'tootasd'
            inserted_text = ''.join(other_args[::2])

            changes.append((index, index, 0, inserted_text))

        # an even smaller wall of text that mostly refers to insert and replace
        elif subcommand == 'replace':
            start, end, *other_args = args
            start = self.index(start)
            end = self.index(end)
            inserted_text = ''.join(other_args[::2])

            # didn't find in docs, but tcl throws an error for this
            assert self.compare(start, '<=', end)

            changes.append((start, end, len(self.get(start, end)),
                            inserted_text))

        else:
            raise ValueError(
                "the tcl code called _change_cb with unexpected subcommand: " +
                subcommand)

        # some plugins expect <<ContentChanged>> events to occur after changing
        # the content in the editor, but the tcl code in __init__ needs them to
        # run before, so here is the solution
        @self.after_idle       # yes, this works
        def this_runs_after_changes():
            for change in changes:
                self.event_generate('<<ContentChanged>>',
                                    data=utils.create_tcl_list(change))

    def _cursor_cb(self):
        # more implicit newline stuff
        new_pos = self.index('insert')
        if new_pos == self.index('end'):
            new_pos = self.index('end - 1 char')

        if new_pos != self._old_cursor_pos:
            self._old_cursor_pos = new_pos
            self.event_generate('<<CursorMoved>>')

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
        self.bind('<parenright>', self._on_closing_brace, add=True)
        self.bind('<bracketright>', self._on_closing_brace, add=True)
        self.bind('<braceright>', self._on_closing_brace, add=True)

        # most other things work by default, but these don't
        self.bind('<Control-v>', self._paste)
        self.bind('<Control-y>', self._redo)
        self.bind('<Control-a>', self._select_all)

        utils.bind_mouse_wheel(self, self._on_ctrl_wheel, prefixes='Control-')

    # TODO: _run.py contains similar code, maybe reuse it here?
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
        font = tkfont.Font(name='TkFixedFont', exists=True)
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

        return None

    def _on_closing_brace(self, event):
        """Dedent automatically."""
        self.dedent('insert')

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
        self.event_generate('<<Redo>>')
        return 'break'

    def _paste(self, event):
        self.event_generate('<<Paste>>')

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
