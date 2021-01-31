"""Allow dragging tabs or pressing keys to change their order."""

import sys
import tkinter
from functools import partial

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

from porcupine import get_main_window, get_tab_manager, tabs, utils


def on_drag(event: 'tkinter.Event[tabs.TabManager]') -> utils.BreakOrNone:
    if event.widget.identify(event.x, event.y) == 'label':
        destination_index = event.widget.index(f'@{event.x},{event.y}')
        event.widget.insert(destination_index, event.widget.select())
        return 'break'
    return None


def select_tab_n(n: int, event: 'tkinter.Event[tkinter.Misc]') -> utils.BreakOrNone:
    try:
        get_tab_manager().select(n - 1)
        return 'break'
    except tkinter.TclError:        # index out of bounds
        return None


def select_left_or_right(diff: Literal[-1, 1]) -> utils.BreakOrNone:
    selected_tab = get_tab_manager().select()
    if selected_tab is not None:
        new_index = get_tab_manager().index(selected_tab) + diff
        try:
            get_tab_manager().select(new_index)
            return 'break'
        except tkinter.TclError:        # index out of bounds
            return None


def move_left_or_right(diff: Literal[-1, 1]) -> utils.BreakOrNone:
    selected_tab = get_tab_manager().select()
    if selected_tab is not None:
        destination_index = get_tab_manager().index(selected_tab) + diff
        try:
            get_tab_manager().insert(destination_index, selected_tab)
            return 'break'
        except tkinter.TclError:        # index out of bounds
            return None


def setup() -> None:
    tabmanager = get_tab_manager()
    tabmanager.bind('<Button1-Motion>', on_drag, add=True)

    # This doesn't use enable_traversal() because we want more bindings than it creates.
    # The bindings also need to be configurable.
    get_main_window().bind('<<TabOrder:SelectLeft>>', (lambda event: select_left_or_right(-1)), add=True)
    get_main_window().bind('<<TabOrder:SelectRight>>', (lambda event: select_left_or_right(1)), add=True)
    get_main_window().bind('<<TabOrder:MoveLeft>>', (lambda event: move_left_or_right(-1)), add=True)
    get_main_window().bind('<<TabOrder:MoveRight>>', (lambda event: move_left_or_right(1)), add=True)

    for n in range(1, 10):
        get_main_window().bind(f'<<TabOrder:SelectTab{n}>>', partial(select_tab_n, n), add=True)

    # TODO: does this work with mac os smooth scrolling? probably not
    utils.bind_mouse_wheel(get_tab_manager(), (
        lambda direction: select_left_or_right({'up': -1, 'down': +1}[direction])  # type: ignore
    ), add=True)
