def trigger_reload(tab):
    tab.textwidget.event_generate("<Button-1>")
    tab.update()


def test_reload_basic(tabmanager, tmp_path):
    (tmp_path / "foo.py").write_text("hello")
    tab = tabmanager.add_file_tab(tmp_path / "foo.py")
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello"

    (tmp_path / "foo.py").write_text("lol")
    trigger_reload(tab)
    assert tab.textwidget.get("1.0", "end - 1 char") == "lol"

    # It should be possible to undo a reload
    tab.textwidget.edit_undo()
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello"


def test_many_lines(tabmanager, tmp_path):
    (tmp_path / "foo.py").write_text("lol\nhello\nlol")
    tab = tabmanager.add_file_tab(tmp_path / "foo.py")

    (tmp_path / "foo.py").write_text("hello")
    trigger_reload(tab)
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello"

    (tmp_path / "foo.py").write_text("hello\nhello\nhello")
    trigger_reload(tab)
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello\nhello\nhello"


def test_tab_switch_triggers_reload(tabmanager, tmp_path):
    (tmp_path / "a.py").write_text("hello")
    (tmp_path / "b.py").write_text("world")
    tab_a = tabmanager.add_file_tab(tmp_path / "a.py")
    tabmanager.add_file_tab(tmp_path / "b.py")

    (tmp_path / "a.py").write_text("new text")
    tabmanager.select(tab_a)
    tabmanager.update()
    assert tab_a.textwidget.get("1.0", "end - 1 char") == "new text"
