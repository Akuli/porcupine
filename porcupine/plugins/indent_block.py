"""If multiple lines are selected and tab is pressed, then indent all of the lines."""
from __future__ import annotations

import tkinter

from porcupine import get_tab_manager, tabs, textwidget, utils

setup_before = ["tabs2spaces"]  # see tabs2spaces.py


def on_tab_key(event: tkinter.Event[textwidget.MainText], shifted: bool) -> None:
    try:
        start_index, end_index = map(str, event.widget.tag_ranges("sel"))
    except ValueError:
        # nothing selected
        return

    start = int(start_index.split(".")[0])
    end = int(end_index.split(".")[0])
    if end_index.split(".")[1] != "0":
        # something's selected on the end line, let's indent/dedent it too
        end += 1

    with textwidget.change_batch(event.widget):
        for lineno in range(start, end):
            if shifted:
                event.widget.dedent(f"{lineno}.0")
            else:
                # if the line is empty or whitespace-only, don't touch it
                if event.widget.get(f"{lineno}.0", f"{lineno}.0 lineend").strip():
                    event.widget.indent(f"{lineno}.0")

    # select only the lines we indented but everything on them
    event.widget.tag_remove("sel", "1.0", "end")
    event.widget.tag_add("sel", f"{start}.0", f"{end}.0")


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        utils.bind_tab_key(tab.textwidget, on_tab_key, add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
