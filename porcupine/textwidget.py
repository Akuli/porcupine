import functools
import operator

import pygments.styles
import teek

from porcupine import settings, utils


class HandyText(teek.Text):
    r"""Like :class:`teek.Text`, but with some handy features.

    All arguments are passed to :class:`teek.Text`.

    .. virtualevent:: ContentChanged

        This event is generated when the text in the widget is modified
        in any way. Unlike ``<<Modified>>``, this event is simply generated
        every time the content changes, and there's no need to unset a flag or
        anything.

        If you want to know what changed and how, pass ``event=True`` to bind,
        and use
        ``event.data((event.widget.Index, event.widget.Index, int, str))`` in
        the callback function. This returns a tuple of 4 elements. The first
        two elements of the tuple are indexes in the text widget before the
        text change occurs, the third element is the number of characters that
        were between the indexes before the change (including newlines) and the
        last value is the new text as a string. For example, if the text widget
        contains ``'hello world'``, then this...
        ::

            # characters 0 to 5 on 1st line are the hello
            textwidget.replace('1.0', '1.5', 'toot')

        ...changes the ``'hello'`` to ``'toot'``, generating a
        ``<<ContentChanged>>`` event with this data::

            (TextIndex(1, 0), TextIndex(1, 5), 5, 'toot')

        Note that the 5 is ``len('hello')``, not ``len('toot')``; it represents
        the length of the **old** text. Unlike you might think, it's actually
        needed for some things.

    .. virtualevent:: CursorMoved

        This event is generated every time the user moves the cursor or
        it's moved with a method of the text widget. Use
        ``textwidget.marks['insert']`` to find the current cursor
        position.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #       /\
        #      /  \  WARNING: serious tk magic coming up
        #     / !! \          proceed at your own risk
        #    /______\
        #
        # this irc conversation might give you an idea of how this works:
        #
        #    <Akuli> __Myst__, why do you want to know how it works?
        #    <__Myst__> Akuli: cause it seems cool
        #    <Akuli> there's 0 reason to docment it in the langserver
        #    <Akuli> ok i can explain :)
        #    <Akuli> in tcl, all statements are command calls
        #    <Akuli> set x lol    ;# set variable x to string lol
        #    <Akuli> set is a command, x and lol are strings
        #    <Akuli> adding stuff to widgets is also command calls
        #    <Akuli> .textwidget insert end hello   ;# add hello to the text
        #            widget
        #    <Akuli> my magic renames the textwidget command to
        #            actual_widget_command, and creates a fake text widget
        #            command that tkinter calls instead
        #    <Akuli> then this fake command checks for all possible widget
        #            commands that can move the cursor or change the content
        #    <Akuli> making sense?
        #    <__Myst__> ooh
        #    <__Myst__> so it's like you're proxying actual calls to the text
        #               widget and calculating change events based on that?
        #    <Akuli> yes
        #    <__Myst__> very cool
        #
        # the irc conversation has gotten a bit outdated:
        #   * it says tkinter, but nowadays porcupine uses teek
        #   * actual_widget_command was self.to_tcl() + '_actual_widget'

        # cursor_cb is called whenever the cursor position may have changed,
        # and change_cb is called whenever the content of the text widget may
        # have changed
        change_cb_command = teek.create_command(self._change_cb, [str],
                                                extra_args_type=str)
        cursor_cb_command = teek.create_command(self._cursor_cb, [])
        self.command_list.append(change_cb_command)
        self.command_list.append(cursor_cb_command)

        # this part is tcl because i couldn't get a python callack to work for
        # some reason
        teek.tcl_eval(None, '''
        rename %(widget)s %(actual_widget)s

        proc %(widget)s {args} {
            #puts $args

            # subcommand is e.g. insert, delete, replace, index, search, ...
            # see text(3tk) for all possible subcommands
            set subcommand [lindex $args 0]

            # issue #5: don't let the cursor to go to the very top or bottom of
            # the view
            if {$subcommand == "see"} {
                # cleaned_index is always a "LINE.COLUMN" string
                set cleaned_index [%(actual_widget)s index [lindex $args 1]]

                # from text(3tk): "If index is far out of view, then the
                # command centers index in the window." and we want to center
                # it correctly, so first go to the center, then a few
                # characters around it, and finally back to center because it
                # feels less error-prone that way
                %(actual_widget)s see $cleaned_index
                %(actual_widget)s see "$cleaned_index - 4 lines"
                %(actual_widget)s see "$cleaned_index + 4 lines"
                %(actual_widget)s see $cleaned_index
                return
            }

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
            'widget': self.to_tcl(),
            'actual_widget': self.to_tcl() + '_actual_widget',
            'change_cb': change_cb_command,
            'cursor_cb': cursor_cb_command,
        })

        # see _cursor_cb
        self._old_cursor_pos = self.marks['insert']

    def _change_cb(self, subcommand, *args):
        # contains (start, end, old_length, new_text) tuples
        changes = []

        # search for 'pathName delete' in text(3tk)... it's a wall of text,
        # and this thing has to implement every detail of that wall
        if subcommand == 'delete':
            # "All indices are first checked for validity before any deletions
            # are made." they are already validated, but rest of this code
            # works with teek TextIndex objects
            # not everything works in corner cases without this
            args = [self.TextIndex.from_tcl(arg) for arg in args]

            # tk has a funny abstraction of an invisible newline character at
            # the end of file, it's always there but nothing else uses it, so
            # let's ignore it
            args = [arg.between_start_end() for arg in args]

            # "If index2 is not specified then the single character at index1
            # is deleted." and later: "If more indices are given, multiple
            # ranges of text will be deleted." but no mention about combining
            # these features, this works like the text widget actually behaves
            if len(args) % 2 == 1:
                args.append(args[-1].forward(chars=1))
            assert len(args) % 2 == 0
            pairs = zip(args[0::2], args[1::2])   # an iterator, not a list yet

            # "If index2 does not specify a position later in the text than
            # index1 then no characters are deleted."
            # note that this also converts pairs to a list
            pairs = [(start, end) for (start, end) in pairs if start < end]

            # "They [index pairs, aka ranges] are sorted [...]."
            pairs.sort(key=operator.itemgetter(0))    # sort by start index

            # "If multiple ranges with the same start index are given, then the
            # longest range is used. If overlapping ranges are given, then they
            # will be merged into spans that do not cause deletion of text
            # outside the given ranges due to text shifted during deletion."
            #
            # this loops through pairs of pairs, and replaces overlapping pairs
            # with their combinations, also works for overlaps of more than
            # 2 pairs
            for i in range(len(pairs)-2, -1, -1):
                (start1, end1), (start2, end2) = pairs[i:i+2]
                if end1 <= start2:
                    # they overlap
                    new_pair = (min(start1, start2), max(end1, end2))
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
            index = self.TextIndex.from_tcl(index)

            # "If index refers to the end of the text (the character after the
            # last newline) then the new text is inserted just before the last
            # newline instead."
            index = index.between_start_end()

            # we don't care about the tagList arguments to insert, but we need
            # to handle the other arguments nicely anyway: "If multiple
            # chars-tagList argument pairs are present, they produce the same
            # effect as if a separate pathName insert widget command had been
            # issued for each pair, in order. The last tagList argument may be
            # omitted." i'm not sure what "in order" means here, but i tried
            # it, and '$textwidget insert 1.0 asd {} toot {}' inserts
            # 'asdtoot', not 'tootasd'
            inserted_text = ''.join(other_args[::2])

            changes.append((index, index, 0, inserted_text))

        # an even smaller wall of text that mostly refers to insert and replace
        elif subcommand == 'replace':
            start, end, *other_args = args
            start = self.TextIndex.from_tcl(start)
            end = self.TextIndex.from_tcl(end)
            inserted_text = ''.join(other_args[::2])

            # didn't find in docs, but tcl throws an error for this
            assert start <= end

            changes.append((start, end, len(self.get(start, end)),
                            inserted_text))

        else:
            raise ValueError(
                "the tcl code called _change_cb with unexpected subcommand: " +
                subcommand)

        # some plugins expect <<ContentChanged>> events to occur after changing
        # the content in the editor, but the tcl code in __init__ needs them to
        # run before, so here is the solution
        @teek.after_idle       # yes, this works
        def this_runs_after_changes():
            for change in changes:
                self.event_generate('<<ContentChanged>>', data=change)

    def _cursor_cb(self):
        # more implicit newline stuff
        new_pos = self.marks['insert'].between_start_end()
        if new_pos != self._old_cursor_pos:
            self._old_cursor_pos = new_pos
            self.event_generate('<<CursorMoved>>')


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

        def on_destroy():
            settings.get_section('General').disconnect(
                'pygments_style', self._set_style)

        self.bind('<Destroy>', on_destroy)

    def _set_style(self, name):
        style = pygments.styles.get_style_by_name(name)
        bg = teek.Color(style.background_color)

        # yes, style.default_style can be '#rrggbb', '' or nonexistent
        # this is undocumented
        #
        #   >>> from pygments.styles import *
        #   >>> [getattr(get_style_by_name(name), 'default_style', '???')
        #   ...  for name in get_all_styles()]
        #   ['', '', '', '', '', '', '???', '???', '', '', '', '',
        #    '???', '???', '', '#cccccc', '', '', '???', '', '', '', '',
        #    '#222222', '', '', '', '???', '']
        if getattr(style, 'default_style', ''):
            fg = teek.Color(style.default_style)
        else:
            fg = utils.invert_color(bg)

        self.config['fg'] = fg
        self.config['bg'] = bg
        self.config['insertbackground'] = fg  # cursor color

        # this is actually not too bad :D
        self.config['selectforeground'] = bg
        self.config['selectbackground'] = fg


class MainText(ThemedText):
    """Don't use this. It may be changed later."""

    # the filetype is needed for setting the tab width and indenting
    def __init__(self, parent, filetype, **kwargs):
        super().__init__(parent, **kwargs)
        self.set_filetype(filetype)

        # FIXME: lots of things have been turned into plugins, but
        # there's still wayyyy too much stuff in here...
        partial = functools.partial     # pep8 line length
        self.bind('<BackSpace>', partial(self._on_delete, False), event=True)
        self.bind('<Control-BackSpace>', partial(self._on_delete, True),
                  event=True)
        self.bind('<Control-Delete>', partial(self._on_delete, True),
                  event=True)
        self.bind('<Shift-Control-Delete>',
                  partial(self._on_delete, True, shifted=True), event=True)
        self.bind('<Shift-Control-BackSpace>',
                  partial(self._on_delete, True, shifted=True), event=True)
        self.bind('<parenright>', self._on_closing_brace)
        self.bind('<bracketright>', self._on_closing_brace)
        self.bind('<braceright>', self._on_closing_brace)

        # most other things work by default, but these don't
        self.bind('<Control-v>', self._paste)
        self.bind('<Control-y>', self._redo)
        self.bind('<Control-a>', self._select_all)

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
        font = teek.NamedFont('TkFixedFont')
        self.config['tabs'] = str(font.measure(' ' * filetype.indent_size))

    def _on_delete(self, control_down, event, *, shifted=False):
        if not self.get_tag('sel').ranges():
            # nothing is selected, we can do non-default stuff
            if control_down and shifted:
                # plan A: delete until end or beginning of line
                # plan B: delete a newline character if there's nothing
                #         to delete with plan A
                cursor = self.marks['insert']
                if event.keysym == 'Delete':
                    plan_a = (cursor, cursor.lineend())
                    plan_b = (cursor, cursor.forward(chars=1))
                else:
                    plan_a = (cursor.linestart(), cursor)
                    plan_b = (cursor.back(chars=1), cursor)

                if plan_a[0] == plan_a[1]:
                    # nothing can be deleted with plan a
                    self.delete(*plan_b)
                else:
                    self.delete(*plan_a)
                return 'break'

            if event.keysym == 'BackSpace':
                before_cursor = self.get(self.marks['insert'].linestart(),
                                         self.marks['insert'])
                if before_cursor and before_cursor.isspace():
                    self.dedent(self.marks['insert'])
                    return 'break'

                if control_down:
                    # delete previous word
                    old_insert = self.marks['insert']
                    self.event_generate('<<PrevWord>>')
                    self.delete(self.marks['insert'], old_insert)
                    return 'break'

            if event.keysym == 'Delete' and control_down:
                # delete next word
                old_insert = self.marks['insert']
                self.event_generate('<<NextWord>>')
                self.delete(old_insert, self.marks['insert'])

        return None

    def _on_closing_brace(self):
        """Dedent automatically."""
        self.dedent(self.marks['insert'])

    def indent(self, location):
        """Insert indentation character(s) at the given location."""
        if not self._filetype.tabs2spaces:
            self.insert(location, '\t')
            return

        # we can't just add ' '*self._filetype.indent_size, for example,
        # if indent_size is 4 and there are 7 charaters we add 1 space
        spaces = self._filetype.indent_size    # pep-8 line length
        spaces2add = spaces - (location.column % spaces)
        self.insert(location, ' ' * spaces2add)

    # FIXME: mixed tabs and spaces don't always work very well
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
            if self.get(location.back(chars=1), location) == '\t':
                self.delete(location.back(chars=1), location)
                return True
            return False

        lineno, column = location
        line = self.get(location.linestart(), location.lineend())

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
        self.delete((lineno, start), (lineno, end))
        return True

    # TODO: is this redo code really needed?
    def _redo(self):
        self.event_generate('<<Redo>>')
        return 'break'

    def _paste(self):
        self.event_generate('<<Paste>>')

        # by default, selected text doesn't go away when pasting
        try:
            [sel_start_end] = self.get_tag('sel').ranges()
        except ValueError:
            # nothing selected
            pass
        else:
            self.delete(*sel_start_end)

        return 'break'

    def _select_all(self):
        self.get_tag('sel').add(self.start, self.end)
        return 'break'

    def iter_chunks(self):
        start = self.start
        while True:
            end = start.forward(chars=1000)
            if start == end:
                break

            yield self.get(start, end)
            start = end
