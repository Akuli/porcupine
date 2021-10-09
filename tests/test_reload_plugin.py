from porcupine import get_tab_manager


def test_reload_basic(tabmanager, tmp_path):
    (tmp_path / "foo.py").write_text("hello")
    tab = tabmanager.open_file(tmp_path / "foo.py")
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello"

    (tmp_path / "foo.py").write_text("lol")
    get_tab_manager().event_generate("<<FileSystemChanged>>")
    assert tab.textwidget.get("1.0", "end - 1 char") == "lol"

    # It should be possible to undo a reload
    tab.textwidget.edit_undo()
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello"


def test_many_lines(tabmanager, tmp_path):
    (tmp_path / "foo.py").write_text("lol\nhello\nlol")
    tab = tabmanager.open_file(tmp_path / "foo.py")

    (tmp_path / "foo.py").write_text("hello")
    get_tab_manager().event_generate("<<FileSystemChanged>>")
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello"

    (tmp_path / "foo.py").write_text("hello\nhello\nhello")
    get_tab_manager().event_generate("<<FileSystemChanged>>")
    assert tab.textwidget.get("1.0", "end - 1 char") == "hello\nhello\nhello"


def test_tab_switch_triggers_reload(tabmanager, tmp_path):
    (tmp_path / "a.py").write_text("hello")
    (tmp_path / "b.py").write_text("world")
    tab_a = tabmanager.open_file(tmp_path / "a.py")
    tabmanager.open_file(tmp_path / "b.py")

    (tmp_path / "a.py").write_text("new text")
    tabmanager.select(tab_a)
    tabmanager.update()
    assert tab_a.textwidget.get("1.0", "end - 1 char") == "new text"
