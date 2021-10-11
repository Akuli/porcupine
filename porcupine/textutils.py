from __future__ import annotations

import contextlib
import dataclasses
import re
import tkinter
import weakref
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Iterator, List, Sequence, overload

from pygments import styles

from porcupine import settings, utils

if TYPE_CHECKING:
    from porcupine import tabs


@dataclasses.dataclass
class Change:
    r"""
    This :mod:`dataclass <dataclasses>` represents any change in a
    :class:`ChangeTrackingText` widget,
    where ``old_text_len`` characters between the text widget indexes ``start``
    and ``end`` get replaced with ``new_text``. For example, this...
    ::

        # let's say that text widget contains 'hello world'
        textwidget.replace('1.0', '1.5', 'toot')

    \...changes the ``'hello'`` to ``'toot'``, and that's represented by a
    ``Change`` like this::

        Change(start=[1, 0], end=[1, 5], old_text_len=5, new_text='toot')

    Insertions are represented with ``Change`` objects having ``old_text_len=0``
    and the same ``start`` and ``end``. For example,
    ``textwidget.insert('1.0', 'hello')`` corresponds to this ``Change``::

        Change(start=[1, 0], end=[1, 0], old_text_len=0, new_text='hello')

    For deletions, ``start`` and ``end`` differ and ``new_text`` is empty.
    If the first line of a text widget contains at least 5 characters, then
    deleting the first 5 characters looks like this::

        Change(start=[1, 0], end=[1, 5], old_text_len=5, new_text='')

    Unlike you might think, the ``old_text_len`` is not redundant. Let's
    say that the text widget contains ``'toot world'`` and all that is
    deleted::

        Change(start=[1, 0], end=[1, 10], old_text_len=10, new_text='')

    In this case, ``old_text_len`` happens to be ``10 - 0``, where ``10`` and
    ``0`` are the column numbers of ``start`` and ``end``. But for changing
    multiple lines, this doesn't work, because you need to know what exactly
    was deleted.

    Technically, ``start=[1, 0]`` is not same as having the change start at
    ``'1.0'``. If there is an embedded window (such as a button widget) at the
    beginning of the line, then the text on the line starts at text index
    ``'1.1'``, represented as ``[1, 0]`` here.
    """
    # These should be Tuple[int, int], but they can't be because converting to
    # json and back turns tuples to lists
    start: List[int]
    end: List[int]
    old_text_len: int
    new_text: str


@dataclasses.dataclass
class Changes(utils.EventDataclass):
    r"""
    This :mod:`dataclass <dataclasses>` represents a list of several
    :class:`Change`\ s applied at once.
    The ``change_list`` is always ordered so that most recent change is
    ``change_list[-1]`` and the oldest change is ``change_list[0]``.

    This boilerplate class is needed instead of a plain ``List[Change]``
    because of how :class:`porcupine.utils.EventDataclass` works.
    """
    change_list: List[Change]


# TODO: document this
def count(widget: tkinter.Text, start: str, end: str, *, option: str = "-chars") -> int:
    # tkinter's .count() method is weird, returns tuples and Nones weirdly
    return widget.tk.call(widget, "count", option, start, end)


class _ChangeTracker:

    # event_receiver_widget will receive the change events
    def __init__(self, event_receiver_widget: tkinter.Text) -> None:
        self._event_receiver_widget = event_receiver_widget
        self._change_batch: list[Change] | None = None

    def setup(self, widget: tkinter.Text) -> None:
        old_cursor_pos = widget.index("insert")  # must be widget specific

        def cursor_pos_changed() -> None:
            nonlocal old_cursor_pos

            new_pos = widget.index("insert")
            if new_pos == widget.index("end"):
                new_pos = widget.index("end - 1 char")

            if new_pos != old_cursor_pos:
                old_cursor_pos = new_pos
                widget.event_generate("<<CursorMoved>>")

        #       /\
        #      /  \  WARNING: serious tkinter magic coming up
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

        # all widget stuff is implemented in python and in tcl as calls to a
        # tcl command named str(widget), and replacing that with a custom
        # command is a very powerful way to do magic; for example, moving the
        # cursor with arrow keys calls the 'mark set' widget command :D
        actual_widget_command = str(widget) + "_actual_widget"
        widget.tk.call("rename", str(widget), actual_widget_command)

        # this part is tcl because i couldn't get a python callback to work
        widget.tk.eval(
            """
        proc %(fake_widget)s {args} {
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

            # only these subcommands can change the text, but they can also
            # move the cursor by changing the text before the cursor
            if {$subcommand == "delete" || $subcommand == "insert" || $subcommand == "replace"} {
                # Validate and clean up indexes here so that any problems
                # result in Tcl error
                if {$subcommand == "delete"} {
                    for {set i 1} {$i < [llength $args]} {incr i} {
                        lset args $i [%(actual_widget)s index [lindex $args $i]]
                    }
                }
                if {$subcommand == "insert"} {
                    lset args 1 [%(actual_widget)s index [lindex $args 1]]
                }
                if {$subcommand == "replace"} {
                    lset args 1 [%(actual_widget)s index [lindex $args 1]]
                    lset args 2 [%(actual_widget)s index [lindex $args 2]]
                }
                set prepared_event [%(change_event_from_command)s {*}$args]
            } else {
                set prepared_event ""
            }

            # it's important that this comes after the change cb stuff because
            # this way it's possible to get old_length in self._change_cb()...
            # however, it's also important that this is before the mark set
            # stuff because the documented way to access the new index in a
            # <<CursorMoved>> binding is getting it directly from the widget
            set result [%(actual_widget)s {*}$args]

            if {$prepared_event != ""} {
                # must be after calling actual widget command
                event generate %(event_receiver)s <<ContentChanged>> -data $prepared_event
            }

            # only[*] 'textwidget mark set insert new_location' can change the
            # cursor position, because the cursor position is implemented as a
            # mark named "insert" and there are no other commands that move
            # marks
            #
            # [*] i lied, hehe >:D MUHAHAHA ... inserting text before the
            # cursor also changes it
            if {[lrange $args 0 2] == {mark set insert} || $prepared_event != ""} {
                %(cursor_moved_callback)s
            }

            return $result
        }
        """
            % {
                "fake_widget": str(widget),
                "actual_widget": actual_widget_command,
                "change_event_from_command": widget.register(
                    partial(self._change_event_from_command, widget)
                ),
                "event_receiver": self._event_receiver_widget,
                "cursor_moved_callback": widget.register(cursor_pos_changed),
            }
        )

    def _create_change(self, widget: tkinter.Text, start: str, end: str, new_text: str) -> Change:
        start_line = int(start.split(".")[0])
        end_line = int(end.split(".")[0])
        return Change(
            start=[start_line, count(widget, f"{start_line}.0", start)],
            end=[end_line, count(widget, f"{end_line}.0", end)],
            old_text_len=len(widget.get(start, end)),
            new_text=new_text,
        )

    # Must be called before widget content actually changes
    def _change_event_from_command(
        self, widget: tkinter.Text, subcommand: str, *args_tuple: str
    ) -> str:
        changes = []

        # search for 'pathName delete' in text(3tk)... it's a wall of text,
        # and this thing has to implement every detail of that wall
        if subcommand == "delete":
            # tk has a funny abstraction of an invisible newline character at
            # the end of file, it's always there but nothing else uses it, so
            # let's ignore it
            args = list(args_tuple)
            for index, old_arg in enumerate(args):
                if old_arg == widget.index("end"):
                    args[index] = widget.index("end - 1 char")

            # "If index2 is not specified then the single character at index1
            # is deleted." and later: "If more indices are given, multiple
            # ranges of text will be deleted." but no mention about combining
            # these features, this works like the text widget actually behaves
            if len(args) % 2 == 1:
                args.append(widget.index(f"{args[-1]} + 1 char"))
            assert len(args) % 2 == 0
            pairs = list(zip(args[0::2], args[1::2]))

            # "If index2 does not specify a position later in the text than
            # index1 then no characters are deleted."
            pairs = [(start, end) for (start, end) in pairs if widget.compare(start, "<", end)]

            # "They [index pairs, aka ranges] are sorted [...]."
            # (line, column) tuples sort nicely
            def get_range_beginning_as_tuple(start_and_end: tuple[str, str]) -> tuple[int, int]:
                line, column = map(int, start_and_end[0].split("."))
                return (line, column)

            pairs.sort(key=get_range_beginning_as_tuple)

            # "If multiple ranges with the same start index are given, then the
            # longest range is used. If overlapping ranges are given, then they
            # will be merged into spans that do not cause deletion of text
            # outside the given ranges due to text shifted during deletion."
            def merge_index_ranges(
                start1: str, end1: str, start2: str, end2: str
            ) -> tuple[str, str]:
                start = start1 if widget.compare(start1, "<", start2) else start2
                end = end1 if widget.compare(end1, ">", end2) else end2
                return (start, end)

            # loop through pairs of pairs
            for i in range(len(pairs) - 2, -1, -1):
                (start1, end1), (start2, end2) = pairs[i : i + 2]
                if widget.compare(end1, ">=", start2):
                    # they overlap
                    new_pair = merge_index_ranges(start1, end1, start2, end2)
                    pairs[i : i + 2] = [new_pair]

            # "[...] and the text is removed from the last range to the first
            # range so deleted text does not cause an undesired index shifting
            # side-effects."
            for start, end in reversed(pairs):
                changes.append(self._create_change(widget, start, end, ""))

        # the man page's inserting section is also kind of a wall of
        # text, but not as bad as the delete
        elif subcommand == "insert":
            text_index, *other_args = args_tuple

            # "If index refers to the end of the text (the character after the
            # last newline) then the new text is inserted just before the last
            # newline instead."
            if text_index == widget.index("end"):
                text_index = widget.index("end - 1 char")

            # we don't care about the tagList arguments to insert, but we need
            # to handle the other arguments nicely anyway: "If multiple
            # chars-tagList argument pairs are present, they produce the same
            # effect as if a separate pathName insert widget command had been
            # issued for each pair, in order. The last tagList argument may be
            # omitted." i'm not sure what "in order" means here, but i tried
            # it, and 'textwidget.insert('1.0', 'asd', [], 'toot', [])' inserts
            # 'asdtoot', not 'tootasd'
            new_text = "".join(other_args[::2])

            changes.append(self._create_change(widget, text_index, text_index, new_text))

        # an even smaller wall of text that mostly refers to insert and replace
        elif subcommand == "replace":
            start, end, *other_args = args_tuple
            new_text = "".join(other_args[::2])

            # more invisible newline garbage
            if start == widget.index("end"):
                start = widget.index("end - 1 char")
            if end == widget.index("end"):
                end = widget.index("end - 1 char")

            # didn't find in docs, but tcl throws an error for this
            assert widget.compare(start, "<=", end)

            changes.append(self._create_change(widget, start, end, new_text))

        else:  # pragma: no cover
            raise ValueError(f"unexpected subcommand: {subcommand}")

        # remove changes that don't actually do anything
        changes = [
            change
            for change in changes
            if change.start != change.end or change.old_text_len != 0 or change.new_text
        ]

        if self._change_batch is None:
            return str(Changes(changes)) if changes else ""
        else:
            self._change_batch.extend(changes)
            return ""  # don't generate event

    def begin_batch(self) -> None:
        if self._change_batch is not None:
            raise RuntimeError("nested calls to change_batch")
        self._change_batch = []

    def finish_batch(self) -> None:
        assert self._change_batch is not None
        try:
            if self._change_batch:
                self._event_receiver_widget.event_generate(
                    "<<ContentChanged>>", data=Changes(self._change_batch)
                )
        finally:
            self._change_batch = None


_change_trackers: weakref.WeakKeyDictionary[
    tkinter.Text, _ChangeTracker
] = weakref.WeakKeyDictionary()


def track_changes(widget: tkinter.Text) -> None:
    """
    Make the text widget emit virtual events whenever its content is modified
    or the cursor moves.

    Don't call this function more than once for the same text widget. Also,
    don't call it yourself for the ``textwidget`` of a
    :class:`~porcupine.tabs.FileTab`, because Porcupine does it automatically.
    You will get a :class:`RuntimeError` if you screw this up.

    .. note::
        Some widget options such as ``undo`` must be set before calling this
        function. Otherwise the changes might not be detected. I don't know
        why that happens and whether it affects other options than ``undo``.

    After calling ``track_changes(widget)``, the text widget has these virtual
    events:

    .. virtualevent:: ContentChanged

        This event is generated when the text in the widget is modified
        in any way. Unlike ``<<Modified>>``, this event is simply generated
        every time the content changes, and there's no need to unset a flag
        like ``textwidget.edit_modified(False)`` or anything like that.

        If you want to know what changed and how, use
        :func:`porcupine.utils.bind_with_data` and
        ``event.data_class(Changes)``. For example, this...
        ::

            # let's say that text widget contains 'hello world'
            textwidget.replace('1.0', '1.5', 'toot')

        ...changes the ``'hello'`` to ``'toot'``, generating a
        ``<<ContentChanged>>`` event whose ``.data_class(Changes)`` returns
        a :class:`Changes` object like this::

            Changes(change_list=[
                Change(start='1.0', end='1.5', old_text_len=5, new_text='toot'),
            ])

        The ``<<ContentChanged>>`` event occurs after the text in the text
        widget has already changed. Also, sometimes many changes are applied
        at once and ``change_list`` contains more than one item.

    .. virtualevent:: CursorMoved

        This event is generated every time the user moves the cursor or
        it's moved with a method of the text widget. Use
        ``textwidget.index('insert')`` to find the current cursor
        position.
    """
    if widget in _change_trackers:
        raise RuntimeError("track_changes() called twice for same text widget")
    if widget.peer_names():
        raise RuntimeError("track_changes() must be called before create_peer_widget()")

    tracker = _ChangeTracker(widget)
    tracker.setup(widget)
    _change_trackers[widget] = tracker


@contextlib.contextmanager
def change_batch(widget: tkinter.Text) -> Iterator[None]:
    """A context manager to optimize doing many changes to a text widget.

    When :func:`track_changes` has been called, every change to a text widget
    generates a new ``<<ContentChanged>>`` event, and lots of
    ``<<ContentChanged>>`` events can cause Porcupine to run slowly. To avoid
    that, you can use this context manager during the changes, like this::

        with textwidget.change_batch(some_text_widget_with_change_tracking):
            for thing in big_list_of_things_to_do:
                textwidget.delete(...)
                textwidget.insert(...)

    This context manager also affects some other things, and so it can be
    useful even with text widgets that don't use :func:`track_changes`:

    * Undoing the whole batch is done with one Ctrl+Z press.
    * When the ``with`` statement ends, the cursor is moved back to where it
      was when the ``with`` statement started.

    See :source:`porcupine/plugins/indent_block.py` for a complete example.
    """
    cursor_pos = widget.index("insert")
    autoseparators_value = widget["autoseparators"]

    try:
        widget.config(autoseparators=False)
        widget.edit_separator()
        try:
            tracker = _change_trackers[widget]
        except KeyError:
            yield
        else:
            tracker.begin_batch()
            try:
                yield
            finally:
                tracker.finish_batch()
        widget.edit_separator()

    finally:
        widget.config(autoseparators=autoseparators_value)
        widget.mark_set("insert", cursor_pos)


def create_peer_widget(
    original_text_widget: tkinter.Text, the_widget_that_becomes_a_peer: tkinter.Text
) -> None:
    """
    Make sure that *the_widget_that_becomes_a_peer* always has the same content
    as *original_text_widget*.

    For details, see the ``PEER WIDGETS`` section in
    `text(3tk) <https://www.tcl.tk/man/tcl8.7/TkCmd/text.htm>`_.
    This is useful for e.g. :source:`porcupine/plugins/minimap.py`.

    .. warning::
        This does **not** create a red text widget::

            the_widget_that_becomes_a_peer = tkinter.Text(master, background='red')
            create_peer_widget(original_text_widget, the_widget_that_becomes_a_peer)

        This works better::

            the_widget_that_becomes_a_peer = tkinter.Text(master)
            create_peer_widget(original_text_widget, the_widget_that_becomes_a_peer)
            the_widget_that_becomes_a_peer.config(background='red')

        All widget options of *the_widget_that_becomes_a_peer* are lost when
        this function is called. I tried to make this function preserve the
        widget options but that caused weird problems.

    Notes about using :func:`create_peer_widget` and :func:`track_changes`
    together:

        * Call :func:`track_changes` with *original_text_widget*, not with its
          peers. If you get this wrong, you will get a :class:`RuntimeError`.
        * Bind to the ``<<ContentChanged>>`` with the original widget, not with
          the peers. If you get this wrong, your ``<<ContentChanged>>``
          callback won't run.
        * First call :func:`track_changes` and then :func:`create_peer_widget`.
          If you get this wrong, you will get a :class:`RuntimeError`.
    """
    # Peer widgets are weird in tkinter. Text.peer_create takes in a
    # widget Tcl name, and then creates a peer widget with that name.
    # But if you want to create a tkinter widget, then you need to let
    # the tkinter widget to create a Tcl widget with a name chosen by
    # tkinter. That has happened already when this function runs.
    #
    # Can't do .destroy() because that screws up winfo_children(). Each tkinter
    # widget knows its child widgets, and .destroy() would make tkinter no
    # longer know it. Tkinter's winfo_children() ignores unknown widgets.
    the_widget_that_becomes_a_peer.tk.call("destroy", the_widget_that_becomes_a_peer)
    original_text_widget.peer_create(the_widget_that_becomes_a_peer)

    change_tracker = _change_trackers.get(original_text_widget)
    if change_tracker is not None:
        change_tracker.setup(the_widget_that_becomes_a_peer)


# http://effbot.org/zone/tkinter-text-hyperlink.htm (use archive.org if needed)
# that tutorial is almost as old as i am, but it's still usable
# TODO: document this?
class LinkManager:
    def __init__(
        self,
        textwidget: tkinter.Text,
        link_regex: str,
        get_click_callback: Callable[[re.Match[str]], Callable[[], object] | None],
    ) -> None:
        self._textwidget = textwidget
        self._link_regex = link_regex
        self._get_click_callback = get_click_callback

        self._callbacks: dict[str, Callable[[], object]] = {}
        textwidget.tag_bind("link", "<Enter>", self._enter_link)
        textwidget.tag_bind("link", "<Leave>", self._leave_link)
        textwidget.tag_bind("link", "<ButtonRelease-1>", self._open_link)

    def _enter_link(self, event: tkinter.Event[tkinter.Text]) -> None:
        self._textwidget.config(cursor="hand2")

    def _leave_link(self, event: tkinter.Event[tkinter.Text]) -> None:
        self._textwidget.config(cursor="")

    def _open_link(self, event: tkinter.Event[tkinter.Text]) -> None:
        for tag in self._textwidget.tag_names("current"):
            if tag.startswith("link-"):
                self._callbacks[tag]()
                break

    # If you add text in parts, make sure that each link is within one part
    def add_links(self, start: str, end: str) -> None:
        for match in re.finditer(self._link_regex, self._textwidget.get(start, end)):
            callback = self._get_click_callback(match)
            if callback is None:
                continue

            link_specific_tag = f"link-{len(self._callbacks)}"
            self._callbacks[link_specific_tag] = callback

            tag_start = f"{start} + {match.start()} chars"
            tag_end = f"{start} + {match.end()} chars"

            self._textwidget.tag_add("link", tag_start, tag_end)
            self._textwidget.tag_add(link_specific_tag, tag_start, tag_end)

    def delete_all_links(self) -> None:
        for tag in self._callbacks.keys():
            self._textwidget.tag_delete(tag)
        self._callbacks.clear()


# fmt: off
@overload
def use_pygments_theme(widget: tkinter.Misc, callback: Callable[[str, str], None]) -> None: ...
@overload
def use_pygments_theme(widget: tkinter.Text, callback: None = ...) -> None: ...
# fmt: on
def use_pygments_theme(
    widget: tkinter.Misc, callback: Callable[[str, str], None] | None = None
) -> None:
    """
    Configure *widget* to use the colors of the Pygments theme whenever the
    currently selected theme changes (see :mod:`porcupine.settings`).
    Porcupine does that automatically for the ``textwidget`` of each
    :class:`~porcupine.tabs.FileTab`.

    If you don't specify a *callback*, then ``widget`` must be a :class:`tkinter.Text` widget.
    If you specify a callback, then it will be called like
    ``callback(foreground_color, background_color)``, and the type of the widget doesn't matter.

    .. seealso::
        This function is used in :source:`porcupine/plugins/linenumbers.py`.
        Syntax highlighting is implemented in
        :source:`porcupine/plugins/highlight.py`.
    """

    def on_style_changed(junk: object = None) -> None:
        style = styles.get_style_by_name(settings.get("pygments_style", str))
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
        fg = getattr(style, "default_style", "") or utils.invert_color(bg)
        if callback is None:
            assert isinstance(widget, tkinter.Text)
            widget.config(
                foreground=fg,
                background=bg,
                insertbackground=fg,  # cursor color
                selectforeground=bg,
                selectbackground=fg,
            )
        else:
            callback(fg, bg)

    widget.bind("<<SettingChanged:pygments_style>>", on_style_changed, add=True)
    on_style_changed()


def config_tab_displaying(
    textwidget: tkinter.Text, indent_size: int, *, tag: str | None = None
) -> None:
    """Make ``textwidget`` display tabs as ``indent_size`` characters wide.

    For example, if ``indent_size`` is 4, then each tab character will look
    like be 4 spaces. This function uses the font of the textwidget, so don't
    change the font immediately after

    If ``tag`` is specified, then only the text tagged with the tag is
    affected, not the entire ``textwidget``.
    """
    if tag is None:
        font = textwidget["font"]
    else:
        font = textwidget.tag_cget(tag, "font") or textwidget["font"]

    # from the text(3tk) man page: "To achieve a different standard
    # spacing, for example every 4 characters, simply configure the
    # widget with “-tabs "[expr {4 * [font measure $font 0]}] left"
    # -tabstyle wordprocessor”."
    measure_result = int(textwidget.tk.call("font", "measure", font, "0"))
    textwidget.config(tabs=(indent_size * measure_result, "left"), tabstyle="wordprocessor")


# TODO: document this?
def bind_font_changed(tab: tabs.FileTab, callback: Callable[[], None]) -> None:
    tab.bind("<<SettingChanged:font_family>>", (lambda event: callback()), add=True)
    tab.bind("<<SettingChanged:font_size>>", (lambda event: callback()), add=True)
    tab.bind("<<TabSettingChanged:indent_size>>", (lambda event: callback()), add=True)


class MainText(tkinter.Text):
    """Don't use this. It may be changed later."""

    def __init__(self, tab: tabs.FileTab, **kwargs: Any) -> None:
        super().__init__(tab.panedwindow, **kwargs)
        self._tab = tab
        track_changes(self)
        use_pygments_theme(self)

        bind_font_changed(tab, self._on_font_changed)
        self._on_font_changed()

        self.bind("<<Dedent>>", (lambda event: self.dedent("insert")), add=True)

    def _on_font_changed(self) -> None:
        config_tab_displaying(self, self._tab.settings.get("indent_size", int))

    def indent(self, location: str) -> None:
        """Insert indentation character(s) at the given location."""
        if not self._tab.settings.get("tabs2spaces", bool):
            self.insert(location, "\t")
            return

        # we can't just add ' '*indent_size, for example,
        # if indent_size is 4 and there are 7 charaters we add 1 space
        indent_size = self._tab.settings.get("indent_size", int)
        how_many_chars = int(self.index(location).split(".")[1])
        space_count = indent_size - (how_many_chars % indent_size)
        self.insert(location, " " * space_count)

    def dedent(self, location: str) -> bool:
        """Remove indentation character(s) if possible.

        This method tries to remove spaces intelligently so that
        everything's lined up evenly based on the indentation settings.
        This method is useful for dedenting whole lines (with location
        set to beginning of the line) or deleting whitespace in the
        middle of a line.

        This returns True if something was done, and False otherwise.
        """
        if not self._tab.settings.get("tabs2spaces", bool):
            if not self.index(location).endswith(".0"):
                # not deleting from start of line, delete previous char instead
                location = f"{location} - 1 char"

            # Deleting spaces this way is annoying. But that is somewhat
            # intentional because mixing tabs and spaces is bad.
            if self.get(location) in {" ", "\t"}:
                self.delete(location)
                return True
            return False

        lineno, column = map(int, self.index(location).split("."))
        line = self.get(f"{location} linestart", f"{location} lineend")

        indent_size = self._tab.settings.get("indent_size", int)
        start = column - (column % indent_size)  # round down to indent_size multiple
        if start == column and start != 0:  # prefer deleting from left side
            start -= indent_size
        assert start >= 0

        # try to delete as much of full indent as possible without going past
        # end of line or deleting non-whitespace
        end = min(start + indent_size, len(line))
        while start < end and not line[start:end].isspace():
            end -= 1

        # location argument must be in the range that gets deleted
        if end < column:
            return False

        assert start <= end
        self.delete(f"{lineno}.{start}", f"{lineno}.{end}")
        return start != end


def create_passive_text_widget(
    parent: tkinter.Misc, is_focusable: bool = False, **kwargs: Any
) -> tkinter.Text:
    # TODO: document `is_focusable` kwarg
    """Create a text widget that is meant to be used for displaying text, not for editing.

    The returned text widget is disabled by default (``state='disabled'``),
    and it's intended to be used that way. You need to temporarily enable it
    to add text to it::

        widget = create_passive_text_widget(parent)
        widget.config(state='normal')
        widget.insert(1.0, wall_of_text)
        widget.config(state='disabled')

    When creating the widget, this function uses some default settings (such as
    ``wrap='word'`` and ``state='disabled'``) that can be overrided with
    ``**kwargs``. For example, the above example code can be written like this::

        widget = create_passive_text_widget(parent, state='normal')
        widget.insert(1.0, wall_of_text)
        widget.config(state='disabled')
    """
    kwargs.setdefault("font", "TkDefaultFont")
    kwargs.setdefault("borderwidth", 0)
    kwargs.setdefault("relief", "flat")
    kwargs.setdefault("wrap", "word")
    kwargs.setdefault("state", "disabled")
    text = tkinter.Text(parent, **kwargs)

    def update_colors(junk: object = None) -> None:
        # tkinter's ttk::style api sucks so let's not use it
        ttk_fg = text.tk.eval("ttk::style lookup TLabel.label -foreground")
        ttk_bg = text.tk.eval("ttk::style lookup TLabel.label -background")

        if not ttk_fg and not ttk_bg:
            # stupid ttk theme, it deserves this
            ttk_fg = "black"
            ttk_bg = "white"
        elif not ttk_bg:
            # this happens with e.g. elegance theme (more_plugins/ttkthemes.py)
            ttk_bg = utils.invert_color(ttk_fg, black_or_white=True)
        elif not ttk_fg:
            ttk_fg = utils.invert_color(ttk_bg, black_or_white=True)

        text.config(foreground=ttk_fg, background=ttk_bg, highlightbackground=ttk_bg)

    if is_focusable:
        text.config(takefocus=True)
        text.bind("<ButtonPress-1>", lambda *junk: text.focus(), add=True)

    # even non-ttk widgets can handle <<ThemeChanged>>
    # TODO: make sure that this works
    text.bind("<<ThemeChanged>>", update_colors, add=True)
    update_colors()

    return text


# TODO: document this?
def get_padding(text: tkinter.Text) -> tuple[int, int]:
    x_padding_on_each_side = text["padx"] + text["borderwidth"] + text["highlightthickness"]
    y_padding_on_each_side = text["pady"] + text["borderwidth"] + text["highlightthickness"]
    return (x_padding_on_each_side, y_padding_on_each_side)


def textwidget_size(text: tkinter.Text) -> tuple[int, int]:
    """Return the width and height of the text widget.

    Unlike ``text.winfo_width()`` and ``text.winfo_height()``,
    this function excludes all padding.
    The size returned by this function is good for scrolling calculations and
    for adding other widgets inside the text widget with ``.place()``.
    """
    x_padding_on_each_side, y_padding_on_each_side = get_padding(text)
    return (
        text.winfo_width() - 2 * x_padding_on_each_side,
        text.winfo_height() - 2 * y_padding_on_each_side,
    )


# TODO: document this?
def place_popup(
    parent: tkinter.Text,
    child: tkinter.Widget,
    *,
    width: int,
    height: int | None = None,
    text_position: str = "insert",
    wrap: bool = False,
) -> bool:
    gap = 5  # Debugging tip: try big gap

    bbox = parent.bbox(text_position)
    if bbox is None:
        # happens quite rarely, just do not place a popup in this case
        return False
    (cursor_x, cursor_y, cursor_width, cursor_height) = bbox

    parent_width, parent_height = textwidget_size(parent)

    # don't go beyond the right edge of textwidget
    width = min(width, parent_width - 2 * gap)

    if wrap:
        assert isinstance(child, tkinter.Label)
        child.config(wraplength=width)  # affects winfo_reqheight()

    if height is None:
        height = child.winfo_reqheight()

    x = min(cursor_x + gap, parent_width - gap - width)
    if cursor_y + cursor_height + gap + height + gap < parent_height:
        # child fits below bbox
        y = cursor_y + cursor_height + gap
    else:
        # would go below bottom of text widget, let's put it above instead
        y = cursor_y - gap - height

    child.place(x=x, y=y, width=width, height=height)
    child.lift()  # autocomplete shows on top of hover popups
    return True
