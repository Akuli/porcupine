"""Comment out multiple lines easily in languages like Python or Bash."""

from porcupine import actions, get_tab_manager, tabs, utils

# update the code if you add a filetype that doesn't use # as comment prefix
filetype_names = ['Python', 'Makefile', 'Shell', 'Tcl']


def comment_or_uncomment():
    tab = get_tab_manager().selected_tab
    if tab.filetype.name not in filetype_names:
        # add '#' normally
        return None

    try:
        [(start_index, end_index)] = tab.textwidget.get_tag('sel').ranges()
    except ValueError as e:
        # nothing selected, add '#' normally
        return None

    start = start_index.line
    end = end_index.line
    if end_index.column != 0:
        # something's selected on the end line, let's (un)comment it too
        end += 1

    gonna_uncomment = all(
        tab.textwidget.get((lineno, 0), (lineno, 1)) == '#'
        for lineno in range(start, end))

    for lineno in range(start, end):
        if gonna_uncomment:
            tab.textwidget.delete((lineno, 0), (lineno, 1))
        else:
            tab.textwidget.insert((lineno, 0), '#')

    # select everything on the (un)commented lines
    tab.textwidget.get_tag('sel').remove()
    tab.textwidget.get_tag('sel').add((start, 0), (end, 0))
    return 'break'


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        # the '#' character is 'numbersign' in tk, lol
        tab.textwidget.bind('<numbersign>', comment_or_uncomment)


def setup():
    # the action's binding feature cannot be used because then typing
    # a '#' outside the main text widget inserts a # to the main widget
    actions.add_command("Edit/Comment Block", comment_or_uncomment,
                        filetype_names=filetype_names)
    get_tab_manager().on_new_tab.connect(on_new_tab)
