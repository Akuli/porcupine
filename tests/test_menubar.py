import platform

import pytest

from porcupine import get_main_window, menubar, tabs, utils
from porcupine.menubar import _get_keyboard_shortcut


def test_get_keyboard_shortcut():
    if platform.system() == 'Darwin':
        # Tk will show these with the proper symbols and stuff
        assert _get_keyboard_shortcut('<Command-c>') == 'Command-c'
        assert _get_keyboard_shortcut('<Mod1-Key-c>') == 'Command-c'
        # TODO: verify if the rest of these are correct:
        assert _get_keyboard_shortcut('<Command-C>') == 'Command-C'
        assert _get_keyboard_shortcut('<Command-Plus>') == 'Command-Plus'
        assert _get_keyboard_shortcut('<Command-Minus>') == 'Command-Minus'
        assert _get_keyboard_shortcut('<Command-0>') == 'Command-0'
        assert _get_keyboard_shortcut('<Command-1>') == 'Command-1'
    else:
        assert _get_keyboard_shortcut('<Control-c>') == 'Ctrl+C'
        assert _get_keyboard_shortcut('<Control-Key-c>') == 'Ctrl+C'
        assert _get_keyboard_shortcut('<Control-C>') == 'Ctrl+Shift+C'
        assert _get_keyboard_shortcut('<Control-Plus>') == 'Ctrl+Plus'
        assert _get_keyboard_shortcut('<Control-Minus>') == 'Ctrl+Minus'
        assert _get_keyboard_shortcut('<Control-0>') == 'Ctrl+Zero'
        assert _get_keyboard_shortcut('<Control-1>') == 'Ctrl+1'

    assert _get_keyboard_shortcut('<F11>') == 'F11'


def test_virtual_events_calling_menu_callbacks():
    called = []
    menubar.get_menu("Foo").add_command(label="Bar", command=(lambda: called.append('bar')))
    menubar.get_menu("Foo").add_command(label="Baz", command=(lambda: called.append('baz')), state='disabled')
    menubar.update_keyboard_shortcuts()
    get_main_window().update()
    get_main_window().event_generate('<<Menubar:Foo/Bar>>')
    get_main_window().event_generate('<<Menubar:Foo/Baz>>')
    assert called == ['bar']


def test_set_enabled_based_on_tab(tabmanager):
    tab1 = tabs.Tab(tabmanager)
    tab2 = tabs.Tab(tabmanager)

    menubar.get_menu("Foo").add_command(label="Spam")
    menubar.set_enabled_based_on_tab("Foo/Spam", (lambda tab: tab is tab2))
    assert menubar.get_menu("Foo").entrycget('end', 'state') == 'disabled'

    tabmanager.add_tab(tab1)
    assert menubar.get_menu("Foo").entrycget('end', 'state') == 'disabled'

    tabmanager.add_tab(tab2)
    assert menubar.get_menu("Foo").entrycget('end', 'state') == 'normal'

    tabmanager.select(tab1)
    tabmanager.update()
    assert menubar.get_menu("Foo").entrycget('end', 'state') == 'disabled'

    tabmanager.close_tab(tab1)
    tabmanager.close_tab(tab2)
    assert menubar.get_menu("Foo").entrycget('end', 'state') == 'disabled'


def test_item_doesnt_exist():
    with pytest.raises(LookupError, match=r"^menu item 'Asdf/BlaBlaBla' not found$"):
        menubar.set_enabled_based_on_tab("Asdf/BlaBlaBla", (lambda tab: True))


def test_text_widget_binding_weirdness(filetab):
    # write text to text widget and select some of it
    filetab.textwidget.insert('1.0', 'hello world')
    filetab.textwidget.tag_add('sel', '1.4', '1.7')

    called = 0

    def fake_can_be_closed():
        nonlocal called
        called += 1
        return False
    filetab.can_be_closed = fake_can_be_closed

    # pressing ctrl+w should leave the text as is (default bindings don't run)
    # and try to close the tab (except that we prevented it from closing)
    filetab.update()
    filetab.textwidget.event_generate(f'<{utils.contmand()}-w>')
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'hello world'
    assert called == 1
