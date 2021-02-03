from porcupine import tabs


def test_reload(tabmanager, tmp_path):
    (tmp_path / 'foo.py').write_text("hello")
    tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'foo.py')
    tabmanager.add_tab(tab, select=True)
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'

    (tmp_path / 'foo.py').write_text('lol')
    tab.textwidget.event_generate('<Button-1>')
    tab.update()
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'lol'

    # It should be possible to undo a reload
    tab.textwidget.edit_undo()
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'
