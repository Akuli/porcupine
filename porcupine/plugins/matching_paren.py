"""
When you put the cursor next to ')', this plugin highlights the matching '('.
"""
from __future__ import annotations

import tkinter
from functools import partial

from porcupine import get_tab_manager, tabs, textwidget, utils

OPEN_TO_CLOSE = {
    '{': '}',
    '[': ']',
    '(': ')',
}
OPEN = OPEN_TO_CLOSE.keys()
CLOSE = OPEN_TO_CLOSE.values()


def on_cursor_moved(event: tkinter.Event[tkinter.Text]) -> None:
    event.widget.tag_remove('matching_paren', '1.0', 'end')

    if event.widget.index('insert') == '1.0':
        # cursor at very start of text widget, no character before cursor
        return

    last_char = event.widget.get('insert - 1 char')
    if last_char in OPEN:
        search_backwards = False
        search_start = 'insert'
    elif last_char in CLOSE:
        search_backwards = True
        search_start = 'insert - 1 char'
    else:
        return

    stack = [last_char]
    while stack:
        match = event.widget.search(
            r'[()\[\]{}]', search_start, ('1.0' if search_backwards else 'end'),
            regexp=True, backwards=search_backwards)
        if not match:
            return   # unclosed parentheses

        paren = event.widget.get(match)
        if (paren in OPEN and not search_backwards) or (paren in CLOSE and search_backwards):
            stack.append(paren)
        elif (paren in CLOSE and not search_backwards) or (paren in OPEN and search_backwards):
            pair = (stack.pop(), paren)
            if pair not in OPEN_TO_CLOSE.items() and pair[::-1] not in OPEN_TO_CLOSE.items():
                # foo([) does not highlight its () because you forgot to close square bracket
                return
        else:
            raise NotImplementedError(paren)
        search_start = match if search_backwards else f'{match} + 1 char'

    event.widget.tag_add('matching_paren', 'insert - 1 char')
    event.widget.tag_add('matching_paren', match)


def on_pygments_theme_changed(text: tkinter.Text, fg: str, bg: str) -> None:
    # use a custom background with a little bit of the theme's foreground mixed in
    text.tag_config('matching_paren', background=utils.mix_colors(fg, bg, 0.2))


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        textwidget.use_pygments_theme(tab, partial(on_pygments_theme_changed, tab.textwidget))
        tab.textwidget.bind('<<CursorMoved>>', on_cursor_moved, add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
