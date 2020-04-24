"""Add a trailing newline character to files when saving."""

from porcupine import get_tab_manager, tabs, utils


def on_save(event):
    textwidget = event.widget.textwidget
    if textwidget.get('end - 2 chars', 'end - 1 char') != '\n':
        # doesn't end with a \n yet, be sure not to annoyingly move the
        # cursor like IDLE does
        cursor = textwidget.index('insert')
        textwidget.insert('end - 1 char', '\n')
        textwidget.mark_set('insert', cursor)


def on_new_tab(event):
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        tab.bind('<<Save>>', on_save, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
