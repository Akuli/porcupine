from porcupine import get_main_window, tabs


def test_reload(tabmanager, tmp_path):
    (tmp_path / 'foo.py').write_text("hello")
    tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'foo.py')
    tabmanager.add_tab(tab, select=True)
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'

    (tmp_path / 'foo.py').write_text('lol')
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'

    get_main_window().event_generate('<<Menubar:File/Reload>>')
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'lol'
