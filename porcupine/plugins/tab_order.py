"""Allow dragging tabs or pressing keys to change their order."""

import tkinter
from functools import partial

from porcupine import get_main_window, get_tab_manager, tabs, utils


def on_drag(event: 'tkinter.Event[tabs.TabManager]') -> None:
    if event.widget.identify(event.x, event.y) == 'label':
        destination_index = event.widget.index(f'@{event.x},{event.y}')
        event.widget.insert(destination_index, event.widget.select())


def on_alt_n(n: int, event: 'tkinter.Event[tkinter.Misc]') -> utils.BreakOrNone:
    try:
        get_tab_manager().select(n - 1)
        return 'break'
    except tkinter.TclError:        # index out of bounds
        return None


# TODO: does this work with mac os smooth scrolling? probably not
def on_wheel(direction: str) -> None:
    get_tab_manager().select_another_tab({'up': -1, 'down': +1}[direction])


def setup() -> None:
    tabmanager = get_tab_manager()
    tabmanager.bind('<Button1-Motion>', on_drag, add=True)

    # This doesn't use enable_traversal() because we want more bindings than it creates.
    get_main_window().bind('<<TabOrder:SelectLeft>>', (lambda event: tabmanager.select_another_tab(-1)), add=True)
    get_main_window().bind('<<TabOrder:SelectRight>>', (lambda event: tabmanager.select_another_tab(1)), add=True)
    get_main_window().bind('<<TabOrder:MoveLeft>>', (lambda event: tabmanager.move_selected_tab(-1)), add=True)
    get_main_window().bind('<<TabOrder:MoveRight>>', (lambda event: tabmanager.move_selected_tab(1)), add=True)

    for n in range(1, 10):
        get_main_window().bind(f'<<TabOrder:SelectTab{n}>>', partial(on_alt_n, n), add=True)

    utils.bind_mouse_wheel(get_tab_manager(), on_wheel, add=True)
