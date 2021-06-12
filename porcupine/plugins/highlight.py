"""Syntax highlighting."""

import itertools
import logging
import time
import tkinter
from tkinter.font import Font
from typing import Any, Callable, Dict, Generator, Iterator, List, Tuple, cast

from pygments import styles, token  # type: ignore[import]
from pygments.lexer import Lexer, LexerMeta, RegexLexer  # type: ignore[import]

from porcupine import get_tab_manager, settings, tabs, textwidget, utils


def _list_all_token_types(tokentype: Any) -> Iterator[Any]:
    yield tokentype
    for sub in map(_list_all_token_types, tokentype.subtypes):
        yield from sub


all_token_tags = set(map(str, _list_all_token_types(token.Token)))
log = logging.getLogger(__name__)
ROOT_STATE_MARK_PREFIX = "highlight_root_"
root_mark_names = (ROOT_STATE_MARK_PREFIX + str(n) for n in itertools.count())


class Highlighter:
    def __init__(self, text: tkinter.Text) -> None:
        self.textwidget = text
        self._lexer = None

        # the tags use fonts from here
        self._fonts: Dict[Tuple[bool, bool], Font] = {}
        for bold in (True, False):
            for italic in (True, False):
                # the fonts will be updated later, see _config_changed()
                self._fonts[(bold, italic)] = Font(
                    weight=("bold" if bold else "normal"), slant=("italic" if italic else "roman")
                )

        self.textwidget.bind("<<SettingChanged:font_family>>", self._font_changed, add=True)
        self.textwidget.bind("<<SettingChanged:font_size>>", self._font_changed, add=True)
        self.textwidget.bind("<<SettingChanged:pygments_style>>", self._style_changed, add=True)
        self._font_changed()
        self._style_changed()

    def _font_changed(self, junk: object = None) -> None:
        font_updates = cast(Dict[str, Any], Font(name="TkFixedFont", exists=True).actual())
        del font_updates["weight"]  # ignore boldness
        del font_updates["slant"]  # ignore italicness

        for (bold, italic), font in self._fonts.items():
            # fonts don't have an update() method
            for key, value in font_updates.items():
                font[key] = value

    def _style_changed(self, junk: object = None) -> None:
        # http://pygments.org/docs/formatterdevelopment/#styles
        # all styles seem to yield all token types when iterated over,
        # so we should always end up with the same tags configured
        style = styles.get_style_by_name(settings.get("pygments_style", str))
        for tokentype, infodict in style:
            # this doesn't use underline and border
            # i don't like random underlines in my code and i don't know
            # how to implement the border with tkinter
            self.textwidget.tag_config(
                str(tokentype),
                font=self._fonts[(infodict["bold"], infodict["italic"])],
                # empty string resets foreground
                foreground=("" if infodict["color"] is None else "#" + infodict["color"]),
                background=("" if infodict["bgcolor"] is None else "#" + infodict["bgcolor"]),
            )

            # make sure that the selection tag takes precedence over our
            # token tag
            self.textwidget.tag_lower(str(tokentype), "sel")

    # yields marks backwards, from end to start
    def _get_root_marks(self, start: str = "1.0", end: str = "end") -> Iterator[str]:
        mark = None
        while True:
            # When stepping backwards, end seems to be excluded. We want to include it.
            mark = self.textwidget.mark_previous(mark or f"{end} + 1 char")
            if mark is None or self.textwidget.compare(mark, "<", start):
                break
            if mark.startswith(ROOT_STATE_MARK_PREFIX):
                yield mark

    def _index_is_marked(self, index: str) -> bool:
        try:
            next(self._get_root_marks(index, index))
        except StopIteration:
            return False
        return True

    def _detect_root_state(self, generator: Generator[Any, Any, Any], end_location: str) -> bool:
        # Only for subclasses of RegexLexer that don't override get_tokens_unprocessed
        # TODO: support ExtendedRegexLexer's context thing
        assert self._lexer is not None
        if type(self._lexer).get_tokens_unprocessed == RegexLexer.get_tokens_unprocessed:
            # Use local variables inside the generator (ugly hack)
            local_vars = generator.gi_frame.f_locals

            # If new_state variable is not None, it will be used to change
            # state after the yielding, and this is not a suitable place for
            # restarting the highlighting later.
            return (
                local_vars["statestack"] == ["root"] and local_vars.get("new_state", None) is None
            )

        # Start of line (column zero) and not indentation or blank line
        return end_location.endswith(".0") and bool(self.textwidget.get(end_location).strip())

    def highlight_range(self, last_possible_start: str, first_possible_end: str = "end") -> None:
        start_time = time.perf_counter()

        assert self._lexer is not None
        start = self.textwidget.index(next(self._get_root_marks(end=last_possible_start), "1.0"))
        lineno, column = map(int, start.split("."))

        end_of_view = self.textwidget.index("@0,10000")
        if self.textwidget.compare(first_possible_end, ">", end_of_view):
            first_possible_end = end_of_view

        tag_locations: Dict[str, List[str]] = {}
        mark_locations = [start]

        # The one time where tk's magic trailing newline is helpful! See #436.
        generator = self._lexer.get_tokens_unprocessed(self.textwidget.get(start, "end"))
        for position, tokentype, text in generator:
            token_start = f"{lineno}.{column}"
            newline_count = text.count("\n")
            if newline_count != 0:
                lineno += newline_count
                column = len(text.rsplit("\n", 1)[-1])
            else:
                column += len(text)
            token_end = f"{lineno}.{column}"
            tag_locations.setdefault(str(tokentype), []).extend([token_start, token_end])

            # We place marks where highlighting may begin.
            # You can't start highlighting anywhere, such as inside a multiline string or comment.
            # The tokenizer is at root state when tokenizing starts.
            # So it has to be in root state for placing a mark.
            if self._detect_root_state(generator, token_end):
                if lineno >= int(mark_locations[-1].split(".")[0]) + 10:
                    mark_locations.append(token_end)
                if self.textwidget.compare(
                    f"{lineno}.{column}", ">=", first_possible_end
                ) and self._index_is_marked(token_end):
                    break

            if self.textwidget.compare(token_end, ">", end_of_view):
                break

        end = f"{lineno}.{column}"
        for tag in all_token_tags:
            self.textwidget.tag_remove(tag, start, end)
        for tag, places in tag_locations.items():
            self.textwidget.tag_add(tag, *places)

        marks_to_unset = []
        for mark in self._get_root_marks(start, end):
            try:
                mark_locations.remove(self.textwidget.index(mark))
            except ValueError:
                marks_to_unset.append(mark)
        self.textwidget.mark_unset(*marks_to_unset)

        for mark_index in mark_locations:
            self.textwidget.mark_set(next(root_mark_names), mark_index)

        mark_count = len(list(self._get_root_marks("1.0", "end")))
        log.debug(
            f"Highlighted between {start} and {end} in"
            f" {round((time.perf_counter() - start_time)*1000)}ms. Root state marks:"
            f" {len(marks_to_unset)} deleted, {len(mark_locations)} added, {mark_count} total"
        )

    def highlight_visible(self, junk: object = None) -> None:
        self.highlight_range(self.textwidget.index("@0,0"))

    def set_lexer(self, lexer: Lexer) -> None:
        self.textwidget.mark_unset(*self._get_root_marks("1.0", "end"))
        self._lexer = lexer
        self.highlight_visible()

    def on_change(self, event: utils.EventWithData) -> None:
        change_list = event.data_class(textwidget.Changes).change_list
        if len(change_list) == 1:
            [change] = change_list
            if len(change.new_text) <= 1:
                # Optimization for typical key strokes (but not for reloading entire file):
                # only highlight the area that might have changed
                self.highlight_range(f"{change.start[0]}.0", f"{change.end[0]}.0 lineend")
                return
        self.highlight_visible()


# When scrolling, don't highlight too often. Makes scrolling smoother.
def debounce(
    any_widget: tkinter.Misc, function: Callable[[], None], ms_between_calls_min: int
) -> Callable[[], None]:
    timeout_scheduled = False
    running_requested = False

    def timeout_callback() -> None:
        nonlocal timeout_scheduled, running_requested
        assert timeout_scheduled
        if running_requested:
            function()
            any_widget.after(ms_between_calls_min, timeout_callback)
            running_requested = False
        else:
            timeout_scheduled = False

    def request_running() -> None:
        nonlocal timeout_scheduled, running_requested
        if timeout_scheduled:
            running_requested = True
        else:
            assert not running_requested
            function()
            any_widget.after(ms_between_calls_min, timeout_callback)
            timeout_scheduled = True

    return request_running


def on_new_filetab(tab: tabs.FileTab) -> None:
    # needed because pygments_lexer might change
    def on_lexer_changed(junk: object = None) -> None:
        assert isinstance(tab, tabs.FileTab)  # f u mypy
        highlighter.set_lexer(tab.settings.get("pygments_lexer", LexerMeta)())

    highlighter = Highlighter(tab.textwidget)
    tab.bind("<<TabSettingChanged:pygments_lexer>>", on_lexer_changed, add=True)
    on_lexer_changed()
    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", highlighter.on_change, add=True)
    utils.add_scroll_command(
        tab.textwidget, "yscrollcommand", debounce(tab, highlighter.highlight_visible, 100)
    )
    highlighter.highlight_visible()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
