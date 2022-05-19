# TODO: test large files
# TODO: offsets are in utf8 bytes, so ä currently messes up everything after on same line
# TODO: integrate compile step, aka build.py, to editor
# TODO: config file stuff
# TODO: docs for config file stuff
# TODO: recurse inside strings? showing f-string contents properly would be nice
# TODO: highlight built-in funcs
from __future__ import annotations

import logging
import tkinter

from typing import Callable
from pygments.lexer import Lexer, LexerMeta
from tree_sitter import Language, Parser, Tree

from porcupine import get_tab_manager, tabs, textutils, utils

log = logging.getLogger(__name__)

parser = Parser()
parser.set_language(Language("build/lang-python.so", "python"))


# If change_range given, only returns nodes that overlap the range
def get_all_nodes(cursor, start_point, end_point):
    overlap_start = max(cursor.node.start_point, start_point)
    overlap_end = min(cursor.node.end_point, end_point)
    if overlap_start >= overlap_end:
        return

    # don't recurse inside strings, for now
    if cursor.node.type != "string" and cursor.goto_first_child():
        yield from get_all_nodes(cursor, start_point, end_point)
        while cursor.goto_next_sibling():
            yield from get_all_nodes(cursor, start_point, end_point)
        cursor.goto_parent()
    else:
        yield cursor.node


def get_tag_name(node) -> str:
    if node.type == "identifier":
        return "Token.Name"
    elif node.type == "comment":
        return "Token.Comment"
    elif node.type == "integer":
        return "Token.Literal.Number.Integer"
    elif node.type == "float":
        return "Token.Literal.Number.Float"
    elif node.type == "string":
        return "Token.Literal.String"
    elif node.type.isidentifier():
        return "Token.Keyword"
    else:
        return "Token.Operator"


class Highlighter:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)
        self._tree: Tree = None

    # tree-sitter has get_changed_ranges() method, but it has a couple problems:
    #   - It returns empty list if you append text to end of a line. But text like that may need to
    #     get highlighted.
    #   - Release version from pypi doesn't have the method.
    def update_tags_of_visible_area_from_tree(self) -> None:
        log.debug("Updating colors of visible part of file")
        start = self.textwidget.index("@0,0")
        end =  self.textwidget.index("@0,10000")
        start_row, start_col = map(int, start.split("."))
        end_row, end_col = map(int, end.split("."))
        start_point = (start_row-1, start_col)
        end_point = (end_row-1, end_col)

        self.textwidget.tag_remove("Token.Name", start, end)
        self.textwidget.tag_remove("Token.Comment", start, end)
        self.textwidget.tag_remove("Token.Literal.Number.Integer", start, end)
        self.textwidget.tag_remove("Token.Literal.Number.Float", start, end)
        self.textwidget.tag_remove("Token.Literal.String", start, end)
        self.textwidget.tag_remove("Token.Keyword", start, end)
        self.textwidget.tag_remove("Token.Operator", start, end)

        for node in list(get_all_nodes(self._tree.walk(), start_point, end_point)):
            tag_name = get_tag_name(node)
            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            self.textwidget.tag_add(
                tag_name, f"{start_row+1}.{start_col}", f"{end_row+1}.{end_col}"
            )

    def reparse_whole_file(self) -> None:
        log.info("Reparsing the whole file from scratch")
        self._tree = parser.parse(self.textwidget.get("1.0", "end - 1 char").encode("utf-8"))

    # FIXME: replace pygments lexers with something else
    def set_lexer(self, lexer: Lexer) -> None:
        self.reparse_whole_file()
        self.update_tags_of_visible_area_from_tree()

    def on_change(self, event: utils.EventWithData) -> None:
        change_list = event.data_class(textutils.Changes).change_list
        if not change_list:
            return

        if len(change_list) >= 2:
            # doesn't happen very often in normal editing
            self.reparse_whole_file()
        else:
            [change] = change_list
            # FIXME: bytes are wrong when text has non-ascii chars
            start_row, start_col = change.start
            old_end_row, old_end_col = change.end
            new_end_row = start_row + change.new_text.count("\n")
            if "\n" in change.new_text:
                new_end_col = len(change.new_text.split("\n")[-1])
            else:
                new_end_col = start_col + len(change.new_text)

            log.debug(f"File changed between {start_row}.{start_col} and {new_end_row}.{new_end_col}, updating")

            start_byte = self.textwidget.tk.call(
                self.textwidget._w, "count", "-chars", "1.0", f"{start_row}.{start_col}"
            )
            self._tree.edit(
                start_byte=start_byte,
                old_end_byte=start_byte + change.old_text_len,
                new_end_byte=start_byte + len(change.new_text),
                start_point=(start_row - 1, start_col),
                old_end_point=(old_end_row - 1, old_end_col),
                new_end_point=(new_end_row - 1, new_end_col),
            )
            self._tree = parser.parse(
                self.textwidget.get("1.0", "end - 1 char").encode("utf-8"), self._tree
            )

        self.update_tags_of_visible_area_from_tree()


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
        highlighter.set_lexer(tab.settings.get("pygments_lexer", LexerMeta)())

    highlighter = Highlighter(tab.textwidget)
    tab.bind("<<TabSettingChanged:pygments_lexer>>", on_lexer_changed, add=True)
    on_lexer_changed()
    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", highlighter.on_change, add=True)
    utils.add_scroll_command(
        tab.textwidget, "yscrollcommand", debounce(tab, highlighter.update_tags_of_visible_area_from_tree, 100)
    )

    highlighter.reparse_whole_file()
    highlighter.update_tags_of_visible_area_from_tree()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
