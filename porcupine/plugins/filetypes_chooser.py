"""Actions for choosing the filetype of the current tab.

The menubar plugin shows these as a "Filetypes" menu.
"""

import functools
from typing import Any, Dict

from porcupine import actions, filetypes, get_tab_manager, tabs


# called when a filetypes menu item is clicked
def set_filetype(filetype: Dict[str, Any]) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    tab.filetype_to_settings(filetype)


def setup() -> None:
    for name in filetypes.get_filetype_names():
        safe_name = name.replace('/', '\\')   # TODO: unicode slash character
        actions.add_command(
            f'Filetypes/{safe_name}',
            functools.partial(set_filetype, filetypes.get_filetype_by_name(name)),
            tabtypes=[tabs.FileTab])
