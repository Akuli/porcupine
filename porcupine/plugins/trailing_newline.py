"""Add a trailing newline character to files when saving."""

import porcupine
from porcupine import tabs


def on_save(event):
    textwidget = event.widget.textwidget
    if textwidget.get('end - 2 chars', 'end - 1 char') != '\n':
        # doesn't end with a \n yet, be sure not to annoyingly move the
        # cursor like IDLE does
        cursor = textwidget.index('insert')
        textwidget.insert('end - 1 char', '\n')
        textwidget.mark_set('insert', cursor)


def on_new_tab(event):
    tab = event.widget.tabs[-1]
    if isinstance(tab, tabs.FileTab):
        tab.bind('<<Save>>', on_save, add=True)


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)
