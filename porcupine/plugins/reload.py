"""Reload file from disk automatically."""
# TODO: this plugin is a bit weird right now, maybe shouldn't be a plugin?
from porcupine import get_tab_manager, tabs


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.bind("<<TabSelected>>", (lambda e: tab.reload_if_necessary()), add=True)
    tab.textwidget.bind("<FocusIn>", (lambda e: tab.reload_if_necessary()), add=True)
    tab.textwidget.bind("<Button-1>", (lambda e: tab.reload_if_necessary()), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
