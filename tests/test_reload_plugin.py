from porcupine import tabs


def trigger_reload(tab):
    tab.textwidget.event_generate('<Button-1>')
    tab.update()


def test_reload_basic(tabmanager, tmp_path):
    (tmp_path / 'foo.py').write_text("hello")
    tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'foo.py')
    tabmanager.add_tab(tab, select=True)
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'

    (tmp_path / 'foo.py').write_text('lol')
    trigger_reload(tab)
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'lol'

    # It should be possible to undo a reload
    tab.textwidget.edit_undo()
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'


def test_many_lines(tabmanager, tmp_path):
    (tmp_path / 'foo.py').write_text("lol\nhello\nlol")
    tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'foo.py')
    tabmanager.add_tab(tab, select=True)

    (tmp_path / 'foo.py').write_text('hello')
    trigger_reload(tab)
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello'

    (tmp_path / 'foo.py').write_text('hello\nhello\nhello')
    trigger_reload(tab)
    assert tab.textwidget.get('1.0', 'end - 1 char') == 'hello\nhello\nhello'


def test_tab_switch_triggers_reload(tabmanager, tmp_path):
    (tmp_path / 'a.py').write_text("hello")
    (tmp_path / 'b.py').write_text("world")
    tab_a = tabs.FileTab.open_file(tabmanager, tmp_path / 'a.py')
    tab_b = tabs.FileTab.open_file(tabmanager, tmp_path / 'b.py')
    tabmanager.add_tab(tab_a, select=True)
    tabmanager.add_tab(tab_b, select=True)

    (tmp_path / 'a.py').write_text("new text")
    tabmanager.select(tab_a)
    tabmanager.update()
    assert tab_a.textwidget.get('1.0', 'end - 1 char') == 'new text'
