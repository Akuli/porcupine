"""Reload file from disk when Ctrl+R is pressed."""
import functools
import tkinter
import typing

from porcupine import get_tab_manager, tabs, utils


def reload(tab: tabs.FileTab, junk: typing.Any) -> utils.BreakOrNone:
    if tab.path is None:
        return None

    cursor_pos = tab.textwidget.index('insert')
    scroll_fraction = tab.textwidget.yview()[0]

    tab.textwidget.delete('1.0', 'end')
    with tab.path.open('r', encoding=tab.settings.get('encoding', str)) as file:
        tab.textwidget.insert('1.0', file.read())
    tab.mark_saved()

    tab.textwidget.mark_set('insert', cursor_pos)
    tab.textwidget.yview_moveto(scroll_fraction)
    return 'break'


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        tab.textwidget.bind('<Control-r>', functools.partial(reload, tab), add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
