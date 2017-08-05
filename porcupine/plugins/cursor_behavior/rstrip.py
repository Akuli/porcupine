"""Remove trailing whitespace when enter is pressed."""

import porcupine
from porcupine import tabs, utils


def after_enter(textwidget):
    """Strip trailing whitespace at the end of a line."""
    lineno = int(textwidget.index('insert').split('.')[0]) - 1
    line = textwidget.get('%d.0' % lineno, '%d.0 lineend' % lineno)
    if len(line) != len(line.rstrip()):
        textwidget.delete('%d.%d' % (lineno, len(line.rstrip())),
                          '%d.0 lineend' % lineno)


def tab_callback(tab):
    if isinstance(tab, tabs.FileTab):
        def bind_callback(event):
            tab.textwidget.after_idle(after_enter, tab.textwidget)

        tab.textwidget.bind('<Return>', bind_callback, add=True)


def setup():
    porcupine.get_tab_manager().new_tab_hook.connect(tab_callback)
