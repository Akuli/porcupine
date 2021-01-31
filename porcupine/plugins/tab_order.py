"""Allow dragging tabs to change their order."""
# TODO: it's too easy to drag a tab slightly up and pop it (see poppingtabs plugin)
# TODO: move ctrl+shift+pageup and ctrl+shift+pagedown and alt+n bindings here and make them configurable

import tkinter

from porcupine import get_tab_manager, tabs


def on_drag(event: 'tkinter.Event[tabs.TabManager]') -> None:
    if event.widget.identify(event.x, event.y) == 'label':
        destination_index = event.widget.index(f'@{event.x},{event.y}')
        event.widget.insert(destination_index, event.widget.select())


def setup() -> None:
    tabmanager = get_tab_manager()
    tabmanager.bind('<Button1-Motion>', on_drag, add=True)
