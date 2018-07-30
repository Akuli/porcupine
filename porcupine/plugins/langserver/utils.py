import os.path
import urllib.request
import select
import typing as t

import sansio_lsp_client as lsp
from porcupine.tabs import FileTab


def tab_uri(tab: FileTab) -> str:
    return "file://" + urllib.request.pathname2url(os.path.abspath(tab.path))


def tab_text(tab: FileTab) -> str:
    return tab.textwidget.get("1.0", "end - 1 char")


def tab_position(tab: FileTab) -> lsp.Position:
    line, column = map(int, tab.textwidget.index("insert").split("."))
    return lsp.Position(line=line - 1, character=column)


def lsp_pos_to_tk_pos(pos: lsp.Position) -> str:
    return "{}.{}".format(pos.line + 1, pos.character)


def tk_pos_to_lsp_pos(pos: str) -> lsp.Position:
    line, character = map(int, pos.split("."))
    return lsp.Position(line = line - 1, character = character)


# XXX(PurpleMyst): I added `case_insensitive` as a keyword parameter because
# `pyls` is case-insensitive, but I'm not sure other language servers are or
# what the spec says.
def find_overlap_start(
    line: int,
    before_cursor: str,
    insert_text: str,
    *,
    case_insensitive: bool = True
) -> str:
    if case_insensitive:
        before_cursor = before_cursor.casefold()
        insert_text = insert_text.casefold()

    for i in range(len(insert_text), -1, -1):
        if before_cursor.endswith(insert_text[:i]):
            break

    start_line = line
    start_character = len(before_cursor) - i
    start = "{}.{}".format(start_line, start_character)

    # FIXME(PurpleMyst): Handle the case that the replacement ends on a different line.
    end_line = line
    end_character = len(before_cursor)
    end = "{}.{}".format(end_line, end_character)

    return (start, end)
