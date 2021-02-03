"""Reload file from disk automatically."""
from porcupine import get_tab_manager, tabs


def reload_if_necessary(tab: tabs.FileTab) -> None:
    if tab.reload_is_needed():
        cursor_pos = tab.textwidget.index('insert')
        scroll_fraction = tab.textwidget.yview()[0]
        tab.reload()   # TODO: error handling?
        tab.textwidget.mark_set('insert', cursor_pos)
        tab.textwidget.yview_moveto(scroll_fraction)


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        filetab = tab   # mypy is wonderful
        tab.textwidget.bind('<<AutoReload>>', (lambda event: reload_if_necessary(filetab)), add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
