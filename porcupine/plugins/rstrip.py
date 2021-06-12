"""Remove trailing whitespace from the end of a line when Enter is pressed."""

import functools

from porcupine import get_tab_manager, tabs


def after_enter(tab: tabs.FileTab) -> None:
    if tab.settings.get("trim_trailing_whitespace", bool):
        lineno = int(tab.textwidget.index("insert").split(".")[0]) - 1
        line = tab.textwidget.get(f"{lineno}.0", f"{lineno}.0 lineend")
        if len(line) != len(line.rstrip()):
            tab.textwidget.delete(f"{lineno}.{len(line.rstrip())}", f"{lineno}.0 lineend")


def on_enter(tab: tabs.FileTab, junk: object) -> None:
    tab.after_idle(after_enter, tab)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("trim_trailing_whitespace", True)
    tab.textwidget.bind("<Return>", functools.partial(on_enter, tab), add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_filetab)
