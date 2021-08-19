import os

from porcupine import tabs


def test_filetab_path_gets_resolved(tmp_path, tabmanager):
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir2").mkdir()
    (tmp_path / "file1").touch()
    (tmp_path / "file2").touch()
    funny1 = tmp_path / "dir1" / ".." / "file1"
    funny2 = tmp_path / "dir2" / ".." / "file2"

    tab = tabs.FileTab(tabmanager, path=funny1)
    assert tab.path != funny1
    assert tab.path.samefile(funny1)
    assert ".." not in tab.path.parts

    tab.path = funny2
    assert tab.path != funny2
    assert tab.path.samefile(funny2)
    assert ".." not in tab.path.parts


def create_files(relative_paths, relative_to):
    paths = [relative_to / relative for relative in relative_paths]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    return paths


def test_same_filename_different_subdirs(tabmanager, tmp_path):
    create_files([f"dir{n}/foo.py" for n in (1, 2, 3, 4)], tmp_path)

    tab1 = tabmanager.open_file(tmp_path / "dir1" / "foo.py")
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "foo.py"

    tab2 = tabmanager.open_file(tmp_path / "dir2" / "foo.py")
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "dir1/foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir2/foo.py"

    tab3 = tabmanager.open_file(tmp_path / "dir3" / "foo.py")
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "dir1/foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir2/foo.py"
    assert tabmanager.tab(tab3, "text").replace(os.sep, "/") == "dir3/foo.py"

    # save as dir4/foo.py
    tab3.path = tmp_path / "dir4" / "foo.py"
    tab3.save()

    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "dir1/foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir2/foo.py"
    assert tabmanager.tab(tab3, "text").replace(os.sep, "/") == "dir4/foo.py"

    tabmanager.close_tab(tab1)
    tabmanager.close_tab(tab2)
    assert tabmanager.tab(tab3, "text").replace(os.sep, "/") == "foo.py"


def test_groupby_bug(tabmanager, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "foo.py").touch()
    (tmp_path / "b" / "foo.py").touch()
    (tmp_path / "asdf.py").touch()

    tab1 = tabmanager.open_file(tmp_path / "a" / "foo.py")
    tab2 = tabmanager.open_file(tmp_path / "asdf.py")
    tab3 = tabmanager.open_file(tmp_path / "b" / "foo.py")

    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "a/foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "asdf.py"
    assert tabmanager.tab(tab3, "text").replace(os.sep, "/") == "b/foo.py"


def test_same_filename_inside_and_outside_subdir(tabmanager, tmp_path):
    foo, dir_slash_foo = create_files(["foo.py", "dir/foo.py"], tmp_path)

    tab1 = tabmanager.open_file(foo)
    tab2 = tabmanager.open_file(dir_slash_foo)
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir/foo.py"


def test_paths_differ_somewhere_in_middle(tabmanager, tmp_path):
    dir1_baz, dir2_baz = create_files(
        ["lol/dir1/foo/bar/baz.py", "lol/dir2/foo/bar/baz.py"], tmp_path
    )

    tab1 = tabmanager.open_file(dir1_baz)
    tab2 = tabmanager.open_file(dir2_baz)
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "dir1/.../baz.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir2/.../baz.py"


def test_new_file_doesnt_show_up_as_modified(filetab):
    assert not filetab.has_unsaved_changes()


def test_other_program_changed_file(filetab, tmp_path):
    assert not filetab.other_program_changed_file()

    filetab.textwidget.insert("1.0", "lol\n")
    assert not filetab.other_program_changed_file()

    filetab.save_as(tmp_path / "foo.py")
    assert not filetab.other_program_changed_file()

    filetab.textwidget.insert("1.0", "x")
    assert not filetab.other_program_changed_file()
    filetab.textwidget.delete("1.0")
    assert not filetab.other_program_changed_file()

    (tmp_path / "foo.py").write_text("wattttttttttt\n")
    assert filetab.other_program_changed_file()

    (tmp_path / "foo.py").write_text("wat\n")
    assert filetab.other_program_changed_file()

    (tmp_path / "foo.py").write_text("lol\n")
    assert not filetab.other_program_changed_file()


def test_save_as(filetab, tmp_path):
    (tmp_path / "foo.py").write_text("hello world\n")
    filetab.path = tmp_path / "foo.py"
    assert filetab.reload()
    filetab.save_as(tmp_path / "bar.py")
    assert (tmp_path / "foo.py").read_text() == "hello world\n"


def test_save_as_title_bug(filetab, tmp_path, tabmanager):
    filetab.save_as(tmp_path / "bar.py")
    assert tabmanager.tab(filetab, "text") == "bar.py"


def test_initial_cursor_pos(tabmanager, tmp_path):
    (tmp_path / "foo.py").write_text("hello")
    tab = tabmanager.open_file(tmp_path / "foo.py")
    assert tab.textwidget.index("insert") == "1.0"


def test_file_becomes_invalid_utf8(tabmanager, tmp_path, mocker):
    mock = mocker.patch("porcupine.tabs._ask_encoding")
    (tmp_path / "foo.py").write_text("asdf")
    tab = tabmanager.open_file(tmp_path / "foo.py")
    assert tab is not None

    (tmp_path / "foo.py").write_text("mörkö", encoding="latin-1")

    mock.return_value = None  # user clicks cancel
    assert not tab.reload()
    mock.assert_called_once()
    assert mock.call_args[0] == (tmp_path / "foo.py", "utf-8")
    assert tab.settings.get("encoding", str) == "utf-8"

    mock.return_value = "latin-1"  # user types the correct encoding and clicks ok
    assert tab.reload()
    assert mock.call_args[0] == (tmp_path / "foo.py", "utf-8")
    assert tab.settings.get("encoding", str) == "latin-1"
    assert tab.textwidget.get("1.0", "end").strip() == "mörkö"


def test_save_encoding_error(tabmanager, tmp_path, mocker):
    wanna_utf8 = mocker.patch("tkinter.messagebox.askyesno")
    (tmp_path / "foo.py").write_text("öää lol", encoding="latin-1")
    (tmp_path / ".editorconfig").write_text("[*.py]\ncharset = latin1\n")

    tab = tabmanager.open_file(tmp_path / "foo.py")
    assert not tab.has_unsaved_changes()
    tab.textwidget.insert("1.2", "Ω")
    assert tab.has_unsaved_changes()
    assert tab.settings.get("encoding", str) == "latin1"

    wanna_utf8.return_value = False
    assert not tab.save()
    assert tab.has_unsaved_changes()
    assert tab.settings.get("encoding", str) == "latin1"

    wanna_utf8.return_value = True
    assert tab.save()
    assert not tab.has_unsaved_changes()
    assert tab.settings.get("encoding", str) == "utf-8"

    assert "Saving failed" in str(wanna_utf8.call_args)
    assert "Ω" in str(wanna_utf8.call_args)
    assert "not a valid character" in str(wanna_utf8.call_args)


def test_read_only_file(tabmanager, tmp_path, mocker, caplog):
    mock = mocker.patch("tkinter.messagebox.showerror")

    (tmp_path / "foo.py").touch()
    (tmp_path / "foo.py").chmod(0o400)  # No idea why this work on windows but ci is green
    assert not tabmanager.open_file(tmp_path / "foo.py").save()

    mock.assert_called_once()
    assert "Saving failed" in str(mock.call_args)
    assert "Make sure that the file is writable" in str(mock.call_args)
    assert "foo.py" in str(mock.call_args)

    [log_record] = caplog.records
    assert log_record.levelname == "ERROR"
