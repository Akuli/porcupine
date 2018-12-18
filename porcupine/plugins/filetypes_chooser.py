"""Actions for choosing the filetype of the current tab.

The menubar plugin shows these as a "Filetypes" menu.
"""

import functools

import pythotk as tk

from porcupine import actions, filetypes, get_tab_manager, tabs


# called when a filetypes menu item is clicked
def var_value_to_tab(var):
    filetype = filetypes.get_filetype_by_name(var.get())
    tab = get_tab_manager().selected_tab
    assert tab is not None
    tab.filetype = filetype


# called when the tab is changed, or something else (e.g. another plugin)
# changes ANY tab's filetype; changing the filetype of some other tab than the
# currently selected tab runs this, but it doesn't matter
def tab_filetype_to_var(var):
    selected_tab = get_tab_manager().selected_tab   # may be None
    if isinstance(selected_tab, tabs.FileTab):
        var.set(selected_tab.filetype.name)


# runs when a new tab is added, there will be no tabs that this hasn't been
# ran for
def on_new_tab(var, tab):
    if isinstance(tab, tabs.FileTab):
        tab.on_filetype_changed.connect(functools.partial(
            tab_filetype_to_var, var))


def setup():
    var = tk.StringVar()

    # this initial value isn't shown anywhere, it just needs to be set to
    # something to avoid an error in actions.add_choice
    var.set(filetypes.get_all_filetypes()[0].name)

    var.write_trace.connect(var_value_to_tab)
    get_tab_manager().bind(
        '<<NotebookTabChanged>>', functools.partial(tab_filetype_to_var, var))
    get_tab_manager().on_new_tab.connect(functools.partial(on_new_tab, var))

    actions.add_choice(
        'Filetypes',
        [filetype.name for filetype in filetypes.get_all_filetypes()],
        var=var, tabtypes=[tabs.FileTab])
