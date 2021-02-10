"""Allow tabs to be closed with "X" button or middle-click."""

import tkinter

from porcupine import get_tab_manager, images, tabs


def close_clicked_tab(event: 'tkinter.Event[tabs.TabManager]') -> None:
    tab = event.widget.tabs()[event.widget.index(f'@{event.x},{event.y}')]
    if tab.can_be_closed():
        event.widget.close_tab(tab)


def on_x_clicked(event: 'tkinter.Event[tabs.TabManager]') -> None:
    if event.widget.identify(event.x, event.y) == 'label':
        # find the right edge of the top label (including close button)
        right = event.x
        while event.widget.identify(right, event.y) == 'label':
            right += 1

        # hopefully the image is on the right edge of the label and there's no padding :O
        if event.x >= right - images.get('closebutton').width():
            close_clicked_tab(event)


# Close tab on middle-click (press down the wheel of the mouse)
def on_tab_clicked(event: 'tkinter.Event[tabs.TabManager]') -> None:
    if event.widget.identify(event.x, event.y) == 'label':
        close_clicked_tab(event)


def setup() -> None:
    tabmanager = get_tab_manager()
    tabmanager.add_tab_callback(lambda tab: get_tab_manager().tab(
        tab, image=images.get('closebutton'), compound='right'
    ))
    tabmanager.bind('<<XButton:CloseWhenCloseButtonClicked>>', on_x_clicked, add=True)
    tabmanager.bind('<<XButton:CloseWhenTabClicked>>', on_tab_clicked, add=True)
