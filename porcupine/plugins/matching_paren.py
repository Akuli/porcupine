from functools import partial
import tkinter

from porcupine import get_tab_manager, tabs, textwidget


OPEN_TO_CLOSE = {
    '{': '}',
    '[': ']',
    '(': ')',
}
OPEN = OPEN_TO_CLOSE.keys()
CLOSE = OPEN_TO_CLOSE.values()


def on_cursor_moved(event: 'tkinter.Event[tkinter.Text]') -> None:
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


# rgb math sucks ikr
def mix_colors(color1: str, color2: str, how_much_color1_out_of_one: float) -> str:
    how_much_color2_out_of_one = 1 - how_much_color1_out_of_one

    widget = get_tab_manager()    # any widget would do
    r, g, b = (
        round(value1*how_much_color1_out_of_one + value2*how_much_color2_out_of_one)
        for value1, value2 in zip(widget.winfo_rgb(color1), widget.winfo_rgb(color2))  # 16-bit color values
    )
    return '#%02x%02x%02x' % (r >> 8, g >> 8, b >> 8)  # convert back to 8-bit


def on_pygments_theme_changed(text: tkinter.Text, fg: str, bg: str) -> None:
    # use a custom background with a little bit of the theme's foreground mixed in
    text.tag_config('matching_paren', background=mix_colors(fg, bg, 0.2))


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        textwidget.use_pygments_theme(tab, partial(on_pygments_theme_changed, tab.textwidget))
        tab.textwidget.bind('<<CursorMoved>>', on_cursor_moved, add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
