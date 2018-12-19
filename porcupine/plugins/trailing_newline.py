"""Add a trailing newline character to files when saving."""

import functools

from porcupine import get_tab_manager, tabs


def on_save(textwidget):
    last_char = textwidget.get(textwidget.end.back(chars=1), textwidget.end)
    if last_char not in {'\n', ''}:
        # doesn't end with a \n yet and is not empty file
        # be sure not to annoyingly move the cursor like IDLE does
        cursor = textwidget.marks['insert']
        textwidget.insert(textwidget.end, '\n')
        textwidget.marks['insert'] = cursor


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        tab.on_save.connect(functools.partial(on_save, tab.textwidget))


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
