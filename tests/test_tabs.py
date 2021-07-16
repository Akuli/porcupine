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

    tab1 = tabs.FileTab.open_file(tabmanager, tmp_path / "dir1" / "foo.py")
    tab2 = tabs.FileTab.open_file(tabmanager, tmp_path / "dir2" / "foo.py")
    tab3 = tabs.FileTab.open_file(tabmanager, tmp_path / "dir3" / "foo.py")

    tabmanager.add_tab(tab1)
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "foo.py"

    tabmanager.add_tab(tab2)
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "dir1/foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir2/foo.py"

    tabmanager.add_tab(tab3)
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
    tabmanager.close_tab(tab3)


def test_same_filename_inside_and_outside_subdir(tabmanager, tmp_path):
    foo, dir_slash_foo = create_files(["foo.py", "dir/foo.py"], tmp_path)

    tab1 = tabs.FileTab.open_file(tabmanager, foo)
    tab2 = tabs.FileTab.open_file(tabmanager, dir_slash_foo)
    tabmanager.add_tab(tab1)
    tabmanager.add_tab(tab2)
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "foo.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir/foo.py"
    tabmanager.close_tab(tab1)
    tabmanager.close_tab(tab2)


def test_paths_differ_somewhere_in_middle(tabmanager, tmp_path):
    dir1_baz, dir2_baz = create_files(
        ["lol/dir1/foo/bar/baz.py", "lol/dir2/foo/bar/baz.py"], tmp_path
    )

    tab1 = tabs.FileTab.open_file(tabmanager, dir1_baz)
    tab2 = tabs.FileTab.open_file(tabmanager, dir2_baz)
    tabmanager.add_tab(tab1)
    tabmanager.add_tab(tab2)
    assert tabmanager.tab(tab1, "text").replace(os.sep, "/") == "dir1/.../baz.py"
    assert tabmanager.tab(tab2, "text").replace(os.sep, "/") == "dir2/.../baz.py"
    tabmanager.close_tab(tab1)
    tabmanager.close_tab(tab2)


def test_new_file_doesnt_show_up_as_modified(filetab):
    assert not filetab.is_modified()


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
    filetab.reload()
    filetab.save_as(tmp_path / "bar.py")
    assert (tmp_path / "foo.py").read_text() == "hello world\n"


def test_save_as_title_bug(filetab, tmp_path, tabmanager):
    filetab.save_as(tmp_path / "bar.py")
    assert tabmanager.tab(filetab, "text") == "bar.py"


def test_initial_cursor_pos(tabmanager, tmp_path):
    (tmp_path / "foo.py").write_text("hello")
    tab = tabs.FileTab.open_file(tabmanager, tmp_path / "foo.py")
    try:
        assert tab.textwidget.index("insert") == "1.0"
    finally:
        tab.destroy()
