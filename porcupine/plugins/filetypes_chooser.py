"""Display the "Filetypes" menu."""

import functools
from typing import Any, Dict

from porcupine import filetypes, menubar, get_tab_manager, tabs


# called when a filetypes menu item is clicked
def set_filetype(filetype: Dict[str, Any]) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    tab.filetype_to_settings(filetype)


def setup() -> None:
    for name in filetypes.get_filetype_names():
        safe_name = name.replace('/', '\\')   # TODO: unicode slash character
        menubar.get_menu("Filetypes").add_command(
            label=safe_name,
            command=functools.partial(set_filetype, filetypes.get_filetype_by_name(name)))
        menubar.set_enabled_based_on_tab(f"Filetypes/{safe_name}", (lambda tab: isinstance(tab, tabs.FileTab)))
