"""Comment out multiple lines easily in languages like Python or Bash."""

import functools
import tkinter
from typing import Optional

from porcupine import actions, get_tab_manager, tabs, utils

# update the code if you add a filetype that doesn't use # as comment prefix
filetype_names = ['Python', 'Makefile', 'Shell', 'Tcl']


def comment_or_uncomment(tab: tabs.FileTab, junk: object = None) -> utils.BreakOrNone:
    if tab.filetype.name not in filetype_names:
        # add '#' normally
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
        tab.textwidget.get('%d.0' % lineno, '%d.1' % lineno) == '#'
        for lineno in range(start, end))

    for lineno in range(start, end):
        if gonna_uncomment:
            tab.textwidget.delete('%d.0' % lineno, '%d.1' % lineno)
        else:
            tab.textwidget.insert('%d.0' % lineno, '#')

    # select everything on the (un)commented lines
    tab.textwidget.tag_remove('sel', '1.0', 'end')
    tab.textwidget.tag_add('sel', '%d.0' % start, '%d.0' % end)
    return 'break'


def comment_or_uncomment_in_current_tab() -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    comment_or_uncomment(tab)


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        # the '#' character seems to be a 'numbersign' in tk
        tab.textwidget.bind(
            '<numbersign>', functools.partial(comment_or_uncomment, tab),
            add=True)


def setup() -> None:
    # the action's binding feature cannot be used because then typing
    # a '#' outside the main text widget inserts a # to the main widget
    actions.add_command(
        "Edit/Comment Block", comment_or_uncomment_in_current_tab,
        filetype_names=filetype_names)
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
