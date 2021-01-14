"""Reload file from disk when Ctrl+R is pressed."""
from typing import Union

from porcupine import get_tab_manager, menubar, tabs


def reload() -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab), repr(tab)
    assert tab.path is not None

    cursor_pos = tab.textwidget.index('insert')
    scroll_fraction = tab.textwidget.yview()[0]

    with tab.path.open('r', encoding=tab.settings.get('encoding', str)) as file:
        content = file.read()

    # Reloading can be undoed with Ctrl+Z
    tab.textwidget.config(autoseparators=False)
    try:
        tab.textwidget.edit_separator()
        tab.textwidget.replace('1.0', 'end', content)
        tab.textwidget.edit_separator()
    finally:
        tab.textwidget.config(autoseparators=True)

    tab.mark_saved()
    tab.textwidget.mark_set('insert', cursor_pos)
    tab.textwidget.yview_moveto(scroll_fraction)


def setup() -> None:
    # Put the reload button before first separator, after "Save As"
    menu = menubar.get_menu('File')
    separator_locations = [i for i in range(menu.index('end') + 1) if menu.type(i) == 'separator']
    index: Union[int, str] = separator_locations[0] if separator_locations else 'end'
    menu.insert_command(index, label='Reload', command=reload)

    update_enabledness = menubar.set_enabled_based_on_tab(
        'File/Reload', (lambda tab: isinstance(tab, tabs.FileTab) and tab.path is not None))
    get_tab_manager().add_tab_callback(lambda tab: tab.bind('<<PathChanged>>', update_enabledness, add=True))
