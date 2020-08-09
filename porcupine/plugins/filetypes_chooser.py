"""Actions for choosing the filetype of the current tab.

The menubar plugin shows these as a "Filetypes" menu.
"""

import functools

from porcupine import actions, filetypes, get_tab_manager, tabs


# called when a filetypes menu item is clicked
def set_filetype(filetype: filetypes.FileType) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    tab.filetype_to_settings(filetype)


def setup() -> None:
    for filetype in filetypes.get_all_filetypes():
        safe_name = filetype.name.replace('/', '\\')   # TODO: unicode slash character
        actions.add_command(
            f'Filetypes/{safe_name}',
            functools.partial(set_filetype, filetype),
            tabtypes=[tabs.FileTab])
