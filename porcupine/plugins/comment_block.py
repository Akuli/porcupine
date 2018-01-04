"""Comment out multiple lines easily in languages like Python or Bash."""

import functools

from porcupine import get_tab_manager, tabs, utils

# update the code if you add a filetype that doesn't use # as comment prefix
filetype_names = ['Python', 'Makefile', 'Shell', 'Tcl']


def comment_or_uncomment(filetab, event):
    if filetab.filetype.name not in filetype_names:
        # add '#' normally
        return None

    try:
        start_index, end_index = map(str, event.widget.tag_ranges('sel'))
    except ValueError as e:
        # nothing selected, add '#' normally
        return None

    start = int(start_index.split('.')[0])
    end = int(end_index.split('.')[0])
    if end_index.split('.')[1] != '0':
        # something's selected on the end line, let's (un)comment it too
        end += 1

    gonna_uncomment = all(
        event.widget.get('%d.0' % lineno, '%d.1' % lineno) == '#'
        for lineno in range(start, end))

    for lineno in range(start, end):
        if gonna_uncomment:
            event.widget.delete('%d.0' % lineno, '%d.1' % lineno)
        else:
            event.widget.insert('%d.0' % lineno, '#')

    # select everything on the (un)commented lines
    event.widget.tag_remove('sel', '1.0', 'end')
    event.widget.tag_add('sel', '%d.0' % start, '%d.0' % end)
    return 'break'


def on_new_tab(event):
    tab = event.data_widget
    if isinstance(tab, tabs.FileTab):
        # the '#' character seems to be a 'numbersign' in tk
        tab.textwidget.bind(
            '<numbersign>', functools.partial(comment_or_uncomment, tab),
            add=True)


def setup():
    # TODO: add an action
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
