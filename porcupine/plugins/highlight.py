# TODO: offsets are in utf8 bytes, so ä currently messes up everything after on same line
# TODO: figure out how strings should work
# TODO: partial highlights efficiently
# TODO: integrate compile step, aka build.py, to editor
# TODO: config file stuff
# TODO: docs for config file stuff
from __future__ import annotations

import logging
import tkinter

from pygments.lexer import Lexer, LexerMeta

from tree_sitter import Language, Parser
from porcupine import get_tab_manager, tabs, textutils, utils


log = logging.getLogger(__name__)

parser = Parser()
parser.set_language(Language("build/lang-python.so", "python"))


def get_all_nodes(cursor):
    if cursor.goto_first_child():
        yield from get_all_nodes(cursor)
        while cursor.goto_next_sibling():
            yield from get_all_nodes(cursor)
        cursor.goto_parent()
    else:
        yield cursor.node


def get_tag_name(node) -> str:
    if node.type == 'identifier':
        return "Token.Name"
    elif node.type == 'comment':
        return "Token.Comment"
    elif node.type == "integer":
        return "Token.Literal.Number.Integer"
    elif node.type == "float":
        return "Token.Literal.Number.Float"
    elif node.type.isidentifier():
        return "Token.Keyword"
    else:
        return "Token.Operator"

class Highlighter:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)

    def highlight_all(self, junk: object = None) -> None:
        print("Highlight!!!")

        self.textwidget.tag_remove("Token.Name", "1.0", "end")
        self.textwidget.tag_remove("Token.Comment", "1.0", "end")
        self.textwidget.tag_remove("Token.Literal.Number.Integer", "1.0", "end")
        self.textwidget.tag_remove("Token.Literal.Number.Float", "1.0", "end")
        self.textwidget.tag_remove("Token.Keyword", "1.0", "end")
        self.textwidget.tag_remove("Token.Operator", "1.0", "end")

        tree = parser.parse(self.textwidget.get("1.0", "end - 1 char").encode("utf-8"))
        for node in get_all_nodes(tree.walk()):
            tag_name = get_tag_name(node)
            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            self.textwidget.tag_add(tag_name, f"{start_row+1}.{start_col}", f"{end_row+1}.{end_col}")

    def set_lexer(self, lexer: Lexer) -> None:
        self._lexer = lexer
        self.highlight_all()

    def on_change(self, event: utils.EventWithData) -> None:
        #change_list = event.data_class(textutils.Changes).change_list
        self.highlight_all()


def on_new_filetab(tab: tabs.FileTab) -> None:
    # needed because pygments_lexer might change
    def on_lexer_changed(junk: object = None) -> None:
        highlighter.set_lexer(tab.settings.get("pygments_lexer", LexerMeta)())

    highlighter = Highlighter(tab.textwidget)
    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", highlighter.on_change, add=True)
    highlighter.highlight_all()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
