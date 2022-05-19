# TODO: bug with writing more text at end of comment
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

from pygments.lexer import Lexer, LexerMeta
from tree_sitter import Language, Parser, Tree

from porcupine import get_tab_manager, tabs, textutils, utils

log = logging.getLogger(__name__)

parser = Parser()
parser.set_language(Language("build/lang-python.so", "python"))


# If change_range given, only returns nodes that overlap the range
def get_all_nodes(cursor, change_range=None):
    if change_range is not None:
        overlap_start = max(cursor.node.start_point, change_range.start_point)
        overlap_end = min(cursor.node.end_point, change_range.end_point)
        if overlap_start >= overlap_end:
            return

    # don't recurse inside strings, for now
    if cursor.node.type != "string" and cursor.goto_first_child():
        yield from get_all_nodes(cursor, change_range)
        while cursor.goto_next_sibling():
            yield from get_all_nodes(cursor, change_range)
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

    def _update_tags_from_tree(self, change_range):
        if change_range is None:
            start = "1.0"
            end = "end"
        else:
            start_row, start_col = change_range.start_point
            end_row, end_col = change_range.end_point
            start = f"{start_row+1}.{start_col}"
            end = f"{end_row+1}.{end_col}"

        self.textwidget.tag_remove("Token.Name", start, end)
        self.textwidget.tag_remove("Token.Comment", start, end)
        self.textwidget.tag_remove("Token.Literal.Number.Integer", start, end)
        self.textwidget.tag_remove("Token.Literal.Number.Float", start, end)
        self.textwidget.tag_remove("Token.Literal.String", start, end)
        self.textwidget.tag_remove("Token.Keyword", start, end)
        self.textwidget.tag_remove("Token.Operator", start, end)

        for node in list(get_all_nodes(self._tree.walk(), change_range)):
            tag_name = get_tag_name(node)
            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            self.textwidget.tag_add(
                tag_name, f"{start_row+1}.{start_col}", f"{end_row+1}.{end_col}"
            )

    def highlight_all(self, junk: object = None) -> None:
        self._tree = parser.parse(self.textwidget.get("1.0", "end - 1 char").encode("utf-8"))
        self._update_tags_from_tree(None)

    def set_lexer(self, lexer: Lexer) -> None:
        self._lexer = lexer
        self.highlight_all()

    def on_change(self, event: utils.EventWithData) -> None:
        change_list = event.data_class(textutils.Changes).change_list
        if not change_list:
            return
        if len(change_list) >= 2:
            # doesn't happen very often in normal editing
            self.highlight_all()
            return
        [change] = change_list

        # FIXME: bytes are wrong when text has non-ascii chars
        start_row, start_col = change.start
        old_end_row, old_end_col = change.end
        new_end_row = start_row + change.new_text.count("\n")
        if "\n" in change.new_text:
            new_end_col = len(change.new_text.split("\n")[-1])
        else:
            new_end_col = start_col + len(change.new_text)

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

        new_tree = parser.parse(
            self.textwidget.get("1.0", "end - 1 char").encode("utf-8"), self._tree
        )
        ranges = self._tree.get_changed_ranges(new_tree)
        self._tree = new_tree

        for changed_range in ranges:
            self._update_tags_from_tree(changed_range)


def on_new_filetab(tab: tabs.FileTab) -> None:
    # needed because pygments_lexer might change
    def on_lexer_changed(junk: object = None) -> None:
        highlighter.set_lexer(tab.settings.get("pygments_lexer", LexerMeta)())

    highlighter = Highlighter(tab.textwidget)
    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", highlighter.on_change, add=True)
    highlighter.highlight_all()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
