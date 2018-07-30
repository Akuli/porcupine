"""Actions for choosing the filetype of the current tab.

The menubar plugin shows these as a "Filetypes" menu.
"""

import functools
import tkinter

from porcupine import actions, filetypes, get_tab_manager, tabs, utils


# called when a filetypes menu item is clicked
def var_value_to_tab(var, *junk):
    filetype = filetypes.get_filetype_by_name(var.get())
    get_tab_manager().select().filetype = filetype


# called when the tab is changed, or something else (e.g. another plugin)
# changes ANY tab's filetype; changing the filetype of some other tab than the
# currently selected tab runs this, but it doesn't matter
def tab_filetype_to_var(var, junk_event):
    selected_tab = get_tab_manager().select()   # may be None
    if isinstance(selected_tab, tabs.FileTab):
        var.set(selected_tab.filetype.name)


# runs when a new tab is added, there will be no tabs that this hasn't been
# ran for
def on_new_tab(var, event):
    the_tab = event.data_widget
    if isinstance(the_tab, tabs.FileTab):
        the_tab.bind('<<FiletypeChanged>>',
                     functools.partial(tab_filetype_to_var, var), add=True)


def setup():
    var = tkinter.StringVar()

    # this initial value isn't shown anywhere, it just needs to be set to
    # something to avoid an error in actions.add_choice
    var.set(filetypes.get_all_filetypes()[0].name)

    var.trace('w', functools.partial(var_value_to_tab, var))
    get_tab_manager().bind(
        '<<NotebookTabChanged>>', functools.partial(tab_filetype_to_var, var),
        add=True)
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>',
                         functools.partial(on_new_tab, var), add=True)

    actions.add_choice(
        'Filetypes',
        [filetype.name for filetype in filetypes.get_all_filetypes()],
        var=var, tabtypes=[tabs.FileTab])
