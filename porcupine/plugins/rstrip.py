"""Remove trailing whitespace when enter is pressed."""

import teek as tk

from porcupine import get_tab_manager, tabs


def after_enter(textwidget):
    """Strip trailing whitespace at the end of a line."""
    line_start = textwidget.marks['insert'].linestart().back(lines=1)
    line = textwidget.get(line_start, line_start.lineend())
    if len(line) != len(line.rstrip()):
        textwidget.delete(
            (line_start.line, len(line.rstrip())), line_start.lineend())


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        def bind_callback():
            tk.after_idle(after_enter, args=[tab.textwidget])

        tab.textwidget.bind('<Return>', bind_callback)


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
