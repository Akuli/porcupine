"""
"Wrap Long Lines" option in the View menu.
"""
import tkinter
from functools import partial

from porcupine import get_tab_manager, menubar, tabs

# unfortunately wrap info be synced between 3 places:
#   - tab settings
#   - tkinter.BooleanVar which is used by the menu bar
#   - textwidget's config


def var_to_settings(var: tkinter.BooleanVar, *junk: object) -> None:
    tab = get_tab_manager().select()
    if isinstance(tab, tabs.FileTab):
        tab.settings.set("wrap", var.get())


def settings_to_var(var: tkinter.BooleanVar, junk: object = None) -> None:
    tab = get_tab_manager().select()
    if isinstance(tab, tabs.FileTab):
        try:
            value = tab.settings.get("wrap", bool)
        except KeyError:
            # Happens when adding new tab to tab manager before on_new_filetab() runs
            return
        var.set(value)
    else:
        var.set(False)  # menu item will be disabled


def settings_to_textwidget(tab: tabs.FileTab, junk: object = None) -> None:
    tab.textwidget.config(wrap=("word" if tab.settings.get("wrap", bool) else "none"))


def on_new_filetab(var: tkinter.BooleanVar, tab: tabs.FileTab) -> None:
    tab.settings.add_option("wrap", False)
    tab.bind("<<TabSettingChanged:wrap>>", partial(settings_to_var, var), add=True)
    tab.bind("<<TabSettingChanged:wrap>>", partial(settings_to_textwidget, tab), add=True)
    settings_to_var(var)
    settings_to_textwidget(tab)


def setup() -> None:
    var = tkinter.BooleanVar()
    var.trace_add("write", partial(var_to_settings, var))
    get_tab_manager().bind("<<NotebookTabChanged>>", partial(settings_to_var, var), add=True)
    menubar.get_menu("View").add_checkbutton(label="Wrap Long Lines", variable=var)
    menubar.set_enabled_based_on_tab(
        "View/Wrap Long Lines", (lambda tab: isinstance(tab, tabs.FileTab))
    )
    get_tab_manager().add_filetab_callback(partial(on_new_filetab, var))
