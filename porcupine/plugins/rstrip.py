"""Remove trailing whitespace from the end of a line when Enter is pressed."""

import functools

from porcupine import get_tab_manager, tabs, utils


def after_enter(tab: tabs.FileTab) -> None:
    if tab.settings.get('trim_trailing_whitespace', bool):
        lineno = int(tab.textwidget.index('insert').split('.')[0]) - 1
        line = tab.textwidget.get(f'{lineno}.0', f'{lineno}.0 lineend')
        if len(line) != len(line.rstrip()):
            tab.textwidget.delete(f'{lineno}.{len(line.rstrip())}', f'{lineno}.0 lineend')


def on_enter(tab: tabs.FileTab, junk: object) -> None:
    tab.after_idle(after_enter, tab)


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        tab.settings.add_option('trim_trailing_whitespace', True)
        tab.textwidget.bind('<Return>', functools.partial(on_enter, tab), add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
