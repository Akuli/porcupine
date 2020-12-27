"""Word Wrap option in View menu."""
from functools import partial
import tkinter

from porcupine import get_tab_manager, menubar, tabs


def on_menu_toggled(wrap_var: tkinter.BooleanVar, *junk: object) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    tab.textwidget.config(wrap=('word' if wrap_var.get() else 'none'))


# return value = whether to enable menu item that changes wrap_var
def on_tab_changed(wrap_var: tkinter.BooleanVar, tab: tabs.Tab) -> bool:
    if isinstance(tab, tabs.FileTab):
        wrap_var.set(tab.textwidget.cget('wrap') == 'word')
        return True
    return False


def setup():
    wrap_var = tkinter.BooleanVar()
    wrap_var.trace_add('write', partial(on_menu_toggled, wrap_var))
    menubar.get_menu("View").add_checkbutton(label="Wrap Long Lines", variable=wrap_var)
    menubar.set_enabled_based_on_tab("View/Wrap Long Lines", partial(on_tab_changed, wrap_var))
