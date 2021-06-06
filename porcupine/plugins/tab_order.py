"""Allow dragging tabs or pressing keys to change their order."""
from __future__ import annotations

import tkinter
from functools import partial

from porcupine import get_main_window, get_tab_manager, tabs, utils


def on_drag(event: tkinter.Event[tabs.TabManager]) -> utils.BreakOrNone:
    if event.widget.identify(event.x, event.y) == "label":  # type: ignore[no-untyped-call]
        destination_index = event.widget.index(f"@{event.x},{event.y}")  # type: ignore[no-untyped-call]
        event.widget.insert(destination_index, event.widget.select())  # type: ignore[no-untyped-call]
        return "break"
    return None


def select_tab_n(n: int, event: tkinter.Event[tkinter.Misc]) -> utils.BreakOrNone:
    try:
        get_tab_manager().select(n - 1)
        return "break"
    except tkinter.TclError:  # index out of bounds
        return None


def select_left_or_right(diff: int) -> utils.BreakOrNone:
    selected_tab = get_tab_manager().select()
    if selected_tab is None:
        return None

    new_index = get_tab_manager().index(selected_tab) + diff  # type: ignore[no-untyped-call]
    try:
        get_tab_manager().select(new_index)
        return "break"
    except tkinter.TclError:  # index out of bounds
        return None


def move_left_or_right(diff: int) -> utils.BreakOrNone:
    selected_tab = get_tab_manager().select()
    if selected_tab is None:
        return None

    destination_index = get_tab_manager().index(selected_tab) + diff  # type: ignore[no-untyped-call]
    try:
        get_tab_manager().insert(destination_index, selected_tab)  # type: ignore[no-untyped-call]
        return "break"
    except tkinter.TclError:  # index out of bounds
        return None


# bigger value --> less sensitive
MACOS_WHEEL_STEP = 2.5

# ignore mouse wheeling when mouse is below this height
WHEEL_Y_MAX = 50


def wheel_callback(diff: int, event: tkinter.Event[tkinter.Misc]) -> None:
    # It's possible to trigger this somewhere else than at top of tab manager
    if event.y < 50:
        select_left_or_right(diff)


def switch_tabs_on_mouse_wheel() -> None:
    tabmanager = get_tab_manager()
    if tabmanager.tk.call("tk", "windowingsystem") == "x11":
        tabmanager.bind("<Button-4>", partial(wheel_callback, -1), add=True)
        tabmanager.bind("<Button-5>", partial(wheel_callback, 1), add=True)

    elif tabmanager.tk.call("tk", "windowingsystem") == "aqua":
        # Handle smooth scrolling
        accumulator = 0.0

        def reset(event: tkinter.Event[tkinter.Misc]) -> None:
            nonlocal accumulator
            accumulator = 0

        def scroll(event: tkinter.Event[tkinter.Misc]) -> None:
            nonlocal accumulator
            accumulator += event.delta
            if accumulator > MACOS_WHEEL_STEP:
                accumulator -= MACOS_WHEEL_STEP
                wheel_callback(-1, event)
            elif accumulator < -MACOS_WHEEL_STEP:
                accumulator += MACOS_WHEEL_STEP
                wheel_callback(1, event)

        tabmanager.bind("<MouseWheel>", scroll, add=True)
        tabmanager.bind("<Leave>", reset, add=True)

    else:  # Windows

        def real_callback(event: tkinter.Event[tkinter.Misc]) -> None:
            if event.delta > 0:
                wheel_callback(-1, event)
            else:
                wheel_callback(1, event)

        tabmanager.bind("<MouseWheel>", real_callback, add=True)


def setup() -> None:
    get_tab_manager().bind("<Button1-Motion>", on_drag, add=True)

    # This doesn't use enable_traversal() because we want more bindings than it creates.
    # The bindings also need to be configurable.
    get_main_window().bind(
        "<<TabOrder:SelectLeft>>", (lambda event: select_left_or_right(-1)), add=True
    )
    get_main_window().bind(
        "<<TabOrder:SelectRight>>", (lambda event: select_left_or_right(1)), add=True
    )
    get_main_window().bind(
        "<<TabOrder:MoveLeft>>", (lambda event: move_left_or_right(-1)), add=True
    )
    get_main_window().bind(
        "<<TabOrder:MoveRight>>", (lambda event: move_left_or_right(1)), add=True
    )

    for n in range(1, 10):
        get_main_window().bind(f"<<TabOrder:SelectTab{n}>>", partial(select_tab_n, n), add=True)

    switch_tabs_on_mouse_wheel()
