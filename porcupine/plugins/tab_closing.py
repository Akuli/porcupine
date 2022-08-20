"""Allow tabs to be closed in different ways."""
from __future__ import annotations

import tkinter
from functools import partial

from porcupine import get_tab_manager, images, tabs


def close_clicked_tab(event: tkinter.Event[tabs.TabManager], *, what2close: str = "this") -> None:
    before = event.widget.index(f"@{event.x},{event.y}")
    after = before + 1

    if what2close == "this":
        tabs = event.widget.tabs()[before:after]
    elif what2close == "left":
        tabs = event.widget.tabs()[:before]
    elif what2close == "right":
        tabs = event.widget.tabs()[after:]
    elif what2close == "others":
        tabs = event.widget.tabs()[:before] + event.widget.tabs()[after:]
    else:
        raise RuntimeError(f"bad what2close value: {what2close}")

    for tab in tabs:
        if tab.can_be_closed():
            event.widget.close_tab(tab)


def on_x_clicked(event: tkinter.Event[tabs.TabManager]) -> None:
    if event.widget.identify(event.x, event.y) == "label":
        # find the right edge of the top label (including close button)
        right = event.x
        while event.widget.identify(right, event.y) == "label":
            right += 1

        # hopefully the image is on the right edge of the label and there's no padding :O
        if event.x >= right - images.get("closebutton").width():
            close_clicked_tab(event)


def show_menu(event: tkinter.Event[tabs.TabManager]) -> None:
    menu = tkinter.Menu(tearoff=False)
    menu.add_command(label="Close this tab", command=partial(close_clicked_tab, event))
    menu.add_command(
        label="Close tabs to left", command=partial(close_clicked_tab, event, what2close="left")
    )
    menu.add_command(
        label="Close tabs to right", command=partial(close_clicked_tab, event, what2close="right")
    )
    menu.add_command(
        label="Close other tabs", command=partial(close_clicked_tab, event, what2close="others")
    )

    menu.tk_popup(event.x_root, event.y_root)
    menu.bind("<Unmap>", (lambda event: menu.after_idle(menu.destroy)), add=True)


# Close tab on middle-click (press down the wheel of the mouse)
def on_header_clicked(event: tkinter.Event[tabs.TabManager]) -> None:
    if event.widget.identify(event.x, event.y) == "label":
        close_clicked_tab(event)


def setup() -> None:
    tabmanager = get_tab_manager()
    tabmanager.add_tab_callback(
        lambda tab: get_tab_manager().tab(tab, image=images.get("closebutton"), compound="right")
    )
    tabmanager.bind("<Button-1>", on_x_clicked, add=True)
    tabmanager.bind("<<RightClick>>", show_menu, add=True)
    tabmanager.bind("<<WheelClick>>", on_header_clicked, add=True)
