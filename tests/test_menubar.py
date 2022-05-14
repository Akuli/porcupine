import os
import sys

import pytest

from porcupine import get_main_window, menubar, tabs


def test_virtual_events_calling_menu_callbacks():
    called = []
    menubar.get_menu("Foo").add_command(label="Bar", command=(lambda: called.append("bar")))
    menubar.get_menu("Foo").add_command(
        label="Baz", command=(lambda: called.append("baz")), state="disabled"
    )
    menubar.update_keyboard_shortcuts()
    get_main_window().update()
    get_main_window().event_generate("<<Menubar:Foo/Bar>>")
    get_main_window().event_generate("<<Menubar:Foo/Baz>>")
    assert called == ["bar"]


def test_set_enabled_based_on_tab(tabmanager):
    tab1 = tabs.Tab(tabmanager)
    tab2 = tabs.Tab(tabmanager)

    menubar.get_menu("Foo").add_command(label="Spam")
    menubar.set_enabled_based_on_tab("Foo/Spam", (lambda tab: tab is tab2))
    assert menubar.get_menu("Foo").entrycget("end", "state") == "disabled"

    tabmanager.add_tab(tab1)
    assert menubar.get_menu("Foo").entrycget("end", "state") == "disabled"

    tabmanager.add_tab(tab2)
    assert menubar.get_menu("Foo").entrycget("end", "state") == "normal"

    tabmanager.select(tab1)
    tabmanager.update()
    assert menubar.get_menu("Foo").entrycget("end", "state") == "disabled"

    tabmanager.close_tab(tab1)
    tabmanager.close_tab(tab2)
    assert menubar.get_menu("Foo").entrycget("end", "state") == "disabled"


def test_item_doesnt_exist():
    with pytest.raises(LookupError, match=r"^menu item 'Asdf/BlaBlaBla' not found$"):
        menubar.set_enabled_based_on_tab("Asdf/BlaBlaBla", (lambda tab: True))


def test_text_widget_binding_weirdness(filetab):
    # write text to text widget and select some of it
    filetab.textwidget.insert("1.0", "hello world")
    filetab.textwidget.tag_add("sel", "1.4", "1.7")

    called = 0

    def fake_can_be_closed():
        nonlocal called
        called += 1
        return False

    filetab.can_be_closed = fake_can_be_closed

    # pressing ctrl+w should leave the text as is (default bindings don't run)
    # and try to close the tab (except that we prevented it from closing)
    filetab.update()
    filetab.textwidget.event_generate("<<Menubar:File/Close>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "hello world"
    assert called == 1


@pytest.mark.skipif(sys.platform != "win32", reason="checks if Windows-specific bug was fixed")
@pytest.mark.xfail(
    os.environ.get("GITHUB_ACTIONS") != "true",
    reason="fails on some computers even though pressing Alt+F4 works",
)
def test_alt_f4_bug_with_filetab(filetab, mocker):
    mock_quit = mocker.patch("porcupine.menubar.quit")
    filetab.textwidget.event_generate("<Alt-F4>")
    mock_quit.assert_called_once_with()


@pytest.mark.skipif(sys.platform != "win32", reason="checks if Windows-specific bug was fixed")
@pytest.mark.xfail(
    os.environ.get("GITHUB_ACTIONS") != "true",
    reason="fails on some computers even though pressing Alt+F4 works",
)
def test_alt_f4_bug_without_filetab(mocker):
    mock_quit = mocker.patch("porcupine.menubar.quit")
    get_main_window().event_generate("<Alt-F4>")
    mock_quit.assert_called_once_with()
