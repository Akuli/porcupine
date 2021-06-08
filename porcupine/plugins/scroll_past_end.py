"""Don't let cursor get to the bottom of the screen before scolling."""

import functools
import tkinter
import typing

from porcupine import get_tab_manager, tabs, utils


# prevents infinite recursion
see_callbacks_blocked = set()


def see_was_called(textwidget: tkinter.Text, index: str) -> None:
    print("see was called", textwidget.yview())
    see_callbacks_blocked.add(textwidget)
    try:
        textwidget.see(f'{index} - 5 lines')
        if textwidget.index(f'{index} + 5 lines') == textwidget.index('end - 1 char'):
            # last line is huge because of the tag, don't show that
            print("aaaa")
            textwidget.see(f'end - 1 line')
        else:
            print("bbbb")
            textwidget.see(f'{index}')
    finally:
        see_callbacks_blocked.remove(textwidget)


# 'pathName see index' in text(3tk) manual page
def see_will_be_called(event: utils.EventWithData) -> None:
    print("see_will_be_called", event.widget.yview())
    if event.widget not in see_callbacks_blocked:
        print("  not blocked", event.widget.yview())
        event.widget.after_idle(see_was_called, event.widget, event.data_string)
    else:
        print("  blocked", event.widget.yview())


def update_scroll_past_end_tag(text: tkinter.Text, junk: typing.Any = None) -> None:
    print('u')
    text.tag_add('scroll_past_end', 'end - 1 line', 'end')
    text.tag_remove('scroll_past_end', '1.0', 'end - 1 line')


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        tab.textwidget.tag_config('scroll_past_end', spacing3=150)
        update_tag = functools.partial(update_scroll_past_end_tag, tab.textwidget)
        tab.textwidget.bind('<<ContentChanged>>', update_tag, add=True)
        update_tag()
        utils.bind_with_data(tab.textwidget, '<<CallingSee>>', see_will_be_called, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
