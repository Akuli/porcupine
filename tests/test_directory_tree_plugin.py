import shutil
import subprocess
import sys
from concurrent.futures import Future
from functools import partial
from pathlib import Path

import pytest

from porcupine import get_paned_window, tabs, utils
from porcupine.plugins import directory_tree as plugin_module
from porcupine.plugins.directory_tree import (
    DirectoryTree,
    _git_pool,
    _path_to_root_inclusive,
    _stringify_path,
    focus_treeview,
    get_path,
)


@pytest.fixture
def tree():
    [tree] = [
        w
        for w in utils.get_children_recursively(get_paned_window())
        if isinstance(w, DirectoryTree)
    ]
    for child in tree.get_children(""):
        tree.delete(child)
    yield tree


@pytest.fixture
def disable_thread_pool(monkeypatch):
    def fake_submit(func):
        fut = Future()
        fut.set_result(func())
        return fut

    monkeypatch.setattr(_git_pool, "submit", fake_submit)


def test_adding_nested_projects(tree, tmp_path):
    def get_paths():
        return [get_path(project) for project in tree.get_children()]

    (tmp_path / "a" / "b").mkdir(parents=True)
    assert get_paths() == []
    tree.add_project(tmp_path / "a")
    assert get_paths() == [tmp_path / "a"]
    tree.add_project(tmp_path / "a" / "b")
    assert get_paths() == [tmp_path / "a" / "b", tmp_path / "a"]
    tree.add_project(tmp_path)
    assert get_paths() == [tmp_path, tmp_path / "a" / "b", tmp_path / "a"]


@pytest.mark.skipif(sys.platform == "win32", reason="rmtree can magically fail on windows")
def test_deleting_project(tree, tmp_path, tabmanager, monkeypatch):
    def get_project_names():
        return [get_path(project).name for project in tree.get_children()]

    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "b").mkdir(parents=True)
    (tmp_path / "a" / "README").touch()
    (tmp_path / "b" / "README").touch()
    a_tab = tabs.FileTab.open_file(tabmanager, tmp_path / "a" / "README")
    b_tab = tabs.FileTab.open_file(tabmanager, tmp_path / "b" / "README")

    tabmanager.add_tab(a_tab)
    assert get_project_names() == ["a"]
    tabmanager.close_tab(a_tab)
    shutil.rmtree(tmp_path / "a")
    tabmanager.add_tab(b_tab)
    assert get_project_names() == ["b"]
    tabmanager.close_tab(b_tab)


def test_autoclose(tree, tmp_path, tabmanager, monkeypatch):
    def get_project_names():
        return [get_path(project).name for project in tree.get_children()]

    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "b").mkdir(parents=True)
    (tmp_path / "c").mkdir(parents=True)
    (tmp_path / "a" / "README").touch()
    (tmp_path / "b" / "README").touch()
    (tmp_path / "c" / "README").touch()
    a_tab = tabs.FileTab.open_file(tabmanager, tmp_path / "a" / "README")
    b_tab = tabs.FileTab.open_file(tabmanager, tmp_path / "b" / "README")
    c_tab = tabs.FileTab.open_file(tabmanager, tmp_path / "c" / "README")
    monkeypatch.setattr(plugin_module, "MAX_PROJECTS", 2)

    assert get_project_names() == []

    tabmanager.add_tab(a_tab)
    assert get_project_names() == ["a"]
    tabmanager.add_tab(b_tab)
    assert get_project_names() == ["b", "a"]
    tabmanager.add_tab(c_tab)
    assert get_project_names() == ["c", "b", "a"]

    tabmanager.close_tab(b_tab)
    assert get_project_names() == ["c", "a"]
    tabmanager.close_tab(c_tab)
    assert get_project_names() == ["c", "a"]
    tabmanager.close_tab(a_tab)
    assert get_project_names() == ["c", "a"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_added_and_modified_content(tree, tmp_path, monkeypatch, disable_thread_pool):
    monkeypatch.chdir(tmp_path)

    subprocess.check_call(["git", "init", "--quiet"], stdout=subprocess.DEVNULL)
    tree.add_project(tmp_path)

    Path("a").write_text("a")
    Path("b").write_text("b")
    subprocess.check_call(["git", "add", "a", "b"])
    Path("b").write_text("lol")
    [project_id] = tree.get_children()

    tree.refresh()
    assert set(tree.item(project_id, "tags")) == {"git_modified"}

    subprocess.check_call(["git", "add", "a", "b"])
    tree.refresh()
    assert set(tree.item(project_id, "tags")) == {"git_added"}


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_merge_conflict(tree, tmp_path, monkeypatch, disable_thread_pool):
    monkeypatch.chdir(tmp_path)

    # Resulting output of 'git log --graph --oneline --all':
    #
    #    * 84dca05 (HEAD -> b) b
    #    | * 9dbd837 (master) a
    #    |/
    #    * e16c2a7 initial
    run = partial(subprocess.run, stdout=subprocess.DEVNULL, shell=True, check=True)
    run("git init --quiet")
    run("git config user.name foo")  # not --global, will stay inside repo
    run("git config user.email foo@bar.baz")
    Path("file").write_text("initial")
    run("git add file")
    run("git commit -m initial")
    Path("file").write_text("a")
    run("git add file")
    run("git commit -m a")
    run("git checkout --quiet -b b HEAD~")  # can't use HEAD^ because ^ is special in windows
    Path("file").write_text("b")
    run("git add file")
    run("git commit -m b")
    run("git merge master", check=False)  # Git returns status 1 when merge conflict occurs

    tree.add_project(tmp_path)
    [project_id] = tree.get_children()
    tree.refresh()
    assert set(tree.item(project_id, "tags")) == {"git_mergeconflict"}


def open_as_if_user_clicked(tree, item):
    tree.selection_set(item)
    tree.item(item, open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()


def test_select_file(tree, monkeypatch, tmp_path, tabmanager, disable_thread_pool):
    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "b").mkdir(parents=True)
    (tmp_path / "a" / "README").touch()
    (tmp_path / "b" / "README").touch()
    (tmp_path / "b" / "file1").touch()
    (tmp_path / "b" / "file2").touch()

    a_readme = tabs.FileTab.open_file(tabmanager, tmp_path / "a" / "README")
    b_file1 = tabs.FileTab.open_file(tabmanager, tmp_path / "b" / "file1")
    b_file2 = tabs.FileTab.open_file(tabmanager, tmp_path / "b" / "file2")
    tabmanager.add_tab(a_readme)
    tabmanager.add_tab(b_file1)
    tabmanager.add_tab(b_file2)
    tree.update()

    tabmanager.select(a_readme)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "a"

    tabmanager.select(b_file1)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b"

    open_as_if_user_clicked(tree, tree.selection()[0])
    tabmanager.select(b_file1)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b" / "file1"

    tabmanager.select(b_file2)
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b" / "file2"

    b_file2.save_as(tmp_path / "b" / "file3")
    tree.update()
    assert get_path(tree.selection()[0]) == tmp_path / "b" / "file3"

    tabmanager.close_tab(a_readme)
    tabmanager.close_tab(b_file1)
    tabmanager.close_tab(b_file2)


def test_focusing_treeview_with_keyboard_updates_selection(tree, tmp_path, disable_thread_pool):
    (tmp_path / "README").touch()
    (tmp_path / "hello.py").touch()
    tree.add_project(tmp_path, refresh=False)
    focus_treeview(tree)
    assert tree.selection()


def test_all_files_deleted(tree, tmp_path, tabmanager, disable_thread_pool):
    (tmp_path / "README").touch()
    (tmp_path / "hello.py").touch()
    tree.add_project(tmp_path)
    project_id = tree.get_children()[0]
    tree.selection_set(project_id)

    # Simulate user opening selected item
    tree.item(tree.selection()[0], open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()
    assert len(tree.get_children(project_id)) == 2

    (tmp_path / "README").unlink()
    (tmp_path / "hello.py").unlink()
    tree.refresh()
    assert tree.contains_dummy(project_id)


def test_nested_projects(tree, tmp_path, tabmanager, disable_thread_pool):
    (tmp_path / "README").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "README").touch()

    tree.add_project(tmp_path)

    [outer_project_id] = [
        project_id for project_id in tree.get_children("") if get_path(project_id) == tmp_path
    ]
    open_as_if_user_clicked(tree, outer_project_id)
    [subdir_inside_other_project] = [
        item_id
        for item_id in tree.get_children(outer_project_id)
        if get_path(item_id) == tmp_path / "subdir"
    ]
    open_as_if_user_clicked(tree, subdir_inside_other_project)

    assert not tree.contains_dummy(subdir_inside_other_project)
    tree.add_project(tmp_path / "subdir")
    assert tree.contains_dummy(subdir_inside_other_project)
    dummy_id = tree.get_children(subdir_inside_other_project)[0]
    assert tree.item(dummy_id, "text") == "(open as a separate project)"


def test_path_to_root_inclusive():
    assert list(_path_to_root_inclusive(Path("foo/bar/baz"), Path("foo"))) == [
        Path("foo/bar/baz"),
        Path("foo/bar"),
        Path("foo"),
    ]
    assert list(_path_to_root_inclusive(Path("foo"), Path("foo"))) == [Path("foo")]


def test_home_folder_displaying():
    assert _stringify_path(Path.home()) == "~"
    assert _stringify_path(Path.home() / "lol") in ["~/lol", r"~\lol"]
    assert "~" not in _stringify_path(Path.home().parent / "asdfggg")
