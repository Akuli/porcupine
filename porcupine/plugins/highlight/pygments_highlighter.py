from __future__ import annotations

import itertools
import tkinter
from typing import Any, Iterator

from pygments.lexer import Lexer, RegexLexer
from pygments.lexers import MarkdownLexer

from porcupine import textutils
from .base_highlighter import BaseHighlighter


ROOT_STATE_MARK_PREFIX = "pygments_root_"
root_mark_names = (ROOT_STATE_MARK_PREFIX + str(n) for n in itertools.count())


class PygmentsHighlighter(BaseHighlighter):
    def __init__(self, textwidget: tkinter.Text, lexer: Lexer) -> None:
        super().__init__(textwidget)
        self.textwidget.mark_unset(*self._get_root_marks("1.0", "end"))
        self._lexer = lexer
        self.highlight_range()

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

    def _detect_root_state(self, generator: Any, end_location: str) -> bool:
        # below code buggy for markdown
        if isinstance(self._lexer, MarkdownLexer):
            return False

        # Only for subclasses of RegexLexer that don't override get_tokens_unprocessed
        # TODO: support ExtendedRegexLexer's context thing
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

    def highlight_range(self, last_possible_start: str = "1.0", first_possible_end: str = "end") -> None:
        # Clamp given start and end to be within the visible part.
        # If no arguments are given, highlight the visible part of the file.
        start_of_view, end_of_view = self.get_visible_part()
        if self.textwidget.compare(last_possible_start, "<", start_of_view):
            last_possible_start = start_of_view
        if self.textwidget.compare(first_possible_end, ">", end_of_view):
            first_possible_end = end_of_view

        start = self.textwidget.index(next(self._get_root_marks(end=last_possible_start), "1.0"))
        lineno, column = map(int, start.split("."))

        tag_locations: dict[str, list[str]] = {}
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
        self.delete_tags(start, end)
        for tag, places in tag_locations.items():
            self.textwidget.tag_add(tag, *places)

        # Update root marks within the range that was processed. This range can
        # be bigger than what was given as arguments, because we made sure to
        # start from a root mark or from the beginning of the file.
        marks_to_unset = []
        for mark in self._get_root_marks(start, end):
            try:
                mark_locations.remove(self.textwidget.index(mark))
            except ValueError:
                marks_to_unset.append(mark)
        self.textwidget.mark_unset(*marks_to_unset)

        for mark_index in mark_locations:
            self.textwidget.mark_set(next(root_mark_names), mark_index)

    def on_scroll(self)->None:
        self.highlight_range()

    def on_change(self, changes: textutils.Changes) -> None:
        if len(changes.change_list) == 1:
            [change] = changes.change_list
            if len(change.new_text) <= 1:
                # Optimization for typical key strokes (but not for reloading entire file):
                # only highlight the area that might have changed
                self.highlight_range(f"{change.start[0]}.0", f"{change.end[0]}.0 lineend")
                return
        self.highlight_range()
