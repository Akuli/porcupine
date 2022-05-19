# convention: row and column both start from 0, row=y before column=x
# potential problem: offsets are in utf8 bytes
# TODO: compile step aka build.py
# TODO: get highlighting whole thing to work
# TODO: partial highlights efficiently
from __future__ import annotations

import logging
import tkinter

from pygments.lexer import Lexer, LexerMeta

from porcupine import get_tab_manager, tabs, textutils, utils


log = logging.getLogger(__name__)


class Highlighter:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)

    def highlight_all(self, junk: object = None) -> None:
        print("Highlight!!!")

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
