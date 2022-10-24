"""Reload file from disk automatically."""
from __future__ import annotations
import tkinter
import weakref

from porcupine import get_tab_manager, tabs, utils
from porcupine.tabs import ReloadInfo


# TODO: should cursor and scrolling stuff be a part of reload() or change_batch()?
def reload_if_necessary(tab: tabs.FileTab) -> None:
    if tab.other_program_changed_file():
        cursor_pos = tab.textwidget.index("insert")
        scroll_fraction = tab.textwidget.yview()[0]
        if tab.reload():
            tab.textwidget.mark_set("insert", cursor_pos)
            tab.textwidget.yview_moveto(scroll_fraction)


error_displayers = weakref.WeakKeyDictionary()


def after_reload(event: tkinter.Event[tabs.FileTab]) -> None:
    tab = event.widget
    info = event.data_class(ReloadInfo)

    if info.error:
        try:
            displayer = error_displayers[tab]
        except KeyError:
            displayer = tkinter.Label(tab.panedwindow, bg="red")
            tab.panedwindow.add(
                displayer,
                after=tab.textwidget,
                sticky=tab.panedwindow.panecget(tab.textwidget, "sticky"),
                stretch=tab.panedwindow.panecget(tab.textwidget, "stretch"),
            )

        tab.panedwindow.paneconfigure(tab.textwidget, hide=True)
        tab.panedwindow.paneconfigure(displayer, hide=False)
        error_displayers[tab] = displayer

    else:
        try:
            displayer = error_displayers[tab]
        except KeyError:
            pass
        else:
            tab.panedwindow.paneconfigure(displayer, hide=True)
            tab.panedwindow.paneconfigure(tab.textwidget, hide=False)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.bind("<<FileSystemChanged>>", (lambda e: reload_if_necessary(tab)), add=True)
    utils.bind_with_data(tab, "<<Reloaded>>", after_reload, add=True)

    # TODO: this a bit slow?
    if tab.path is not None:
        tab.reload()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
