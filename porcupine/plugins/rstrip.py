"""Remove trailing whitespace from the end of a line when Enter is pressed."""

import tkinter

from porcupine import get_tab_manager, tabs, utils


def after_enter(textwidget: tkinter.Text) -> None:
    """Strip trailing whitespace at the end of a line."""
    lineno = int(textwidget.index('insert').split('.')[0]) - 1
    line = textwidget.get('%d.0' % lineno, '%d.0 lineend' % lineno)
    if len(line) != len(line.rstrip()):
        textwidget.delete('%d.%d' % (lineno, len(line.rstrip())),
                          '%d.0 lineend' % lineno)


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        textwidget = tab.textwidget

        def bind_callback(event: tkinter.Event) -> None:
            textwidget.after_idle(after_enter, textwidget)

        textwidget.bind('<Return>', bind_callback, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
