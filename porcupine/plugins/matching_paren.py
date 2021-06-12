"""
When you put the cursor next to ')', this plugin highlights the matching '('.
"""
from __future__ import annotations

import re
import tkinter
from functools import partial

from porcupine import get_tab_manager, tabs, textwidget, utils

OPEN_TO_CLOSE = {"{": "}", "[": "]", "(": ")"}
CLOSE_TO_OPEN = {close: open_ for open_, close in OPEN_TO_CLOSE.items()}


def on_cursor_moved(event: tkinter.Event[tkinter.Text]) -> None:
    event.widget.tag_remove("matching_paren", "1.0", "end")

    if event.widget.index("insert") == "1.0" or event.widget.get("insert - 2 chars") == "\\":
        # cursor at very start of text widget or backslash escape found
        return

    last_char = event.widget.get("insert - 1 char")
    cursor_line, cursor_column = map(int, event.widget.index("insert").split("."))
    stack = [last_char]

    # Tkinter's .search() is slow when there are lots of tags from highlight plugin.
    # See "PERFORMANCE ISSUES" in text widget manual page
    if last_char in OPEN_TO_CLOSE.keys():
        backwards = False
        text = event.widget.get("insert", "end - 1 char")
        regex = r"(?<!\\)[()\[\]{}]"
        mapping = CLOSE_TO_OPEN
    elif last_char in OPEN_TO_CLOSE.values():
        backwards = True
        text = event.widget.get("1.0", "insert - 1 char")[::-1]
        regex = r"[()\[\]{}](?!\\)"
        mapping = OPEN_TO_CLOSE
    else:
        return

    for match in re.finditer(regex, text):
        char = match.group()
        if char not in mapping:
            assert char in mapping.values()
            stack.append(char)
            continue

        if stack.pop() != mapping[char]:
            return
        if not stack:
            if backwards:
                lineno = 1 + text.count("\n", match.end())
                if lineno == 1:
                    column = len(text) - match.end()
                else:
                    column = text.index("\n", match.end()) - match.end()
            else:
                lineno = cursor_line + text.count("\n", 0, match.start())
                if lineno == cursor_line:
                    column = cursor_column + match.start()
                else:
                    column = match.start() - text.rindex("\n", 0, match.start()) - 1
            event.widget.tag_add("matching_paren", "insert - 1 char")
            event.widget.tag_add("matching_paren", f"{lineno}.{column}")
            break


def on_pygments_theme_changed(text: tkinter.Text, fg: str, bg: str) -> None:
    # use a custom background with a little bit of the theme's foreground mixed in
    text.tag_config("matching_paren", background=utils.mix_colors(fg, bg, 0.2))


def on_new_filetab(tab: tabs.FileTab) -> None:
        textwidget.use_pygments_theme(tab, partial(on_pygments_theme_changed, tab.textwidget))
        tab.textwidget.bind("<<CursorMoved>>", on_cursor_moved, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
