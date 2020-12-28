"""If you select multiple lines and type '#', then all selected lines are commented out."""
# TODO: don't assume that '#' comments are a thing in every programming language

import functools

from porcupine import get_tab_manager, menubar, tabs, utils


def comment_or_uncomment(tab: tabs.FileTab, junk: object = None) -> utils.BreakOrNone:
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


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        # the '#' character seems to be a 'numbersign' in tk
        tab.textwidget.bind(
            '<numbersign>', functools.partial(comment_or_uncomment, tab),
            add=True)


def setup() -> None:
    # the action's binding feature cannot be used because then typing
    # a '#' outside the main text widget inserts a # to the main widget
    menubar.get_menu("Edit").add_command(label="Comment Block", command=comment_or_uncomment_in_current_tab)
    menubar.set_enabled_based_on_tab("Edit/Comment Block", (lambda tab: isinstance(tab, tabs.FileTab)))
    get_tab_manager().add_tab_callback(on_new_tab)
