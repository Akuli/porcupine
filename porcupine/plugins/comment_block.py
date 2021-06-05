"""
If you select multiple lines in a Python file and type '#', then all selected
lines are commented out.

A different character is used in other programming languages. This can be
configured with comment_prefix in filetypes.toml.
"""
from __future__ import annotations

import functools
import tkinter
from typing import Optional

from porcupine import get_tab_manager, menubar, tabs, textwidget, utils


def comment_or_uncomment(
    tab: tabs.FileTab, event: Optional[tkinter.Event[tkinter.Text]]
) -> utils.BreakOrNone:
    comment_prefix = tab.settings.get('comment_prefix', Optional[str])
    if event is not None and event.char != comment_prefix:
        return None

    try:
        start_index, end_index = map(str, tab.textwidget.tag_ranges('sel'))
    except ValueError:
        # nothing selected, add '#' normally
        return None

    start = int(start_index.split('.')[0])
    end = int(end_index.split('.')[0])
    if end_index.split('.')[1] != '0':
        # something's selected on the end line, let's (un)comment it too
        end += 1

    gonna_uncomment = all(
        tab.textwidget.get(f'{lineno}.0', f'{lineno}.1') == comment_prefix
        for lineno in range(start, end)
    )

    with textwidget.change_batch(tab.textwidget):
        for lineno in range(start, end):
            if gonna_uncomment:
                tab.textwidget.delete(f'{lineno}.0', f'{lineno}.1')
            else:
                tab.textwidget.insert(f'{lineno}.0', comment_prefix)

    # select everything on the (un)commented lines
    tab.textwidget.tag_remove('sel', '1.0', 'end')
    tab.textwidget.tag_add('sel', f'{start}.0', f'{end}.0')
    return 'break'


def comment_or_uncomment_in_current_tab() -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    comment_or_uncomment(tab, None)


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        tab.textwidget.bind('<Key>', functools.partial(comment_or_uncomment, tab), add=True)


def setup() -> None:
    # the action's binding feature cannot be used because then typing
    # a '#' outside the main text widget inserts a # to the main widget
    menubar.get_menu("Edit").add_command(
        label="Comment Block", command=comment_or_uncomment_in_current_tab
    )
    menubar.set_enabled_based_on_tab(
        "Edit/Comment Block", (lambda tab: isinstance(tab, tabs.FileTab))
    )
    get_tab_manager().add_tab_callback(on_new_tab)
