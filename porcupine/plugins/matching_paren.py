"""
When you put the cursor next to ')', this plugin highlights the matching '('.
"""
from __future__ import annotations

import re
import tkinter
from functools import partial

from porcupine import get_tab_manager, tabs, textwidget, utils

OPEN_TO_CLOSE = {
    '{': '}',
    '[': ']',
    '(': ')',
}
CLOSE_TO_OPEN = {close: open_ for open_, close in OPEN_TO_CLOSE.items()}
OPEN = OPEN_TO_CLOSE.keys()
CLOSE = OPEN_TO_CLOSE.values()


def on_cursor_moved(event: tkinter.Event[tkinter.Text]) -> None:
    event.widget.tag_remove('matching_paren', '1.0', 'end')

    if event.widget.index('insert') == '1.0' or event.widget.get('insert - 2 chars') == '\\':
        # cursor at very start of text widget or backslash escape found
        return

    last_char = event.widget.get('insert - 1 char')
    if last_char in OPEN:
        # Tkinter's .search() is slow when there are lots of tags from highlight plugin.
        # See "PERFORMANCE ISSUES" in text widget manual page
        text = event.widget.get('insert', 'end - 1 char')

        lineno, cursor_column = map(int, event.widget.index('insert').split('.'))

        stack = [last_char]
        for match in re.finditer(r'(?<!\\)[()\[\]{}]|\n', text):
            char = match.group()
            if char == '\n':
                lineno += 1
            elif char in OPEN:
                stack.append(char)
            elif char in CLOSE:
                if stack.pop() != CLOSE_TO_OPEN[char]:
                    # foo([) does not highlight its () because you forgot to close square bracket
                    return
                if not stack:
                    try:
                        column = match.start() - text.rindex('\n', 0, match.start()) - 1
                    except ValueError:
                        column = cursor_column + match.start()
                    break
        else:
            return

    elif last_char in CLOSE:
        text = event.widget.get('1.0', 'insert - 1 char')[::-1]
        lineno, cursor_column = map(int, event.widget.index('insert').split('.'))

        stack = [last_char]
        for match in re.finditer(r'[()\[\]{}](?!\\)|\n', text):
            char = match.group()
            if char == '\n':
                lineno -= 1
            elif char in CLOSE:
                stack.append(char)
            elif char in OPEN:
                if stack.pop() != OPEN_TO_CLOSE[char]:
                    return
                if not stack:
                    try:
                        column = text.index('\n', match.end()) - match.end()
                    except ValueError:
                        column = len(text) - match.end()
                    break
        else:
            return

    else:
        return

    event.widget.tag_add('matching_paren', 'insert - 1 char')
    event.widget.tag_add('matching_paren', f'{lineno}.{column}')


def on_pygments_theme_changed(text: tkinter.Text, fg: str, bg: str) -> None:
    # use a custom background with a little bit of the theme's foreground mixed in
    text.tag_config('matching_paren', background=utils.mix_colors(fg, bg, 0.2))


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        textwidget.use_pygments_theme(tab, partial(on_pygments_theme_changed, tab.textwidget))
        tab.textwidget.bind('<<CursorMoved>>', on_cursor_moved, add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
