from functools import partial
import shutil
import subprocess

import pytest

from porcupine.plugins.directory_tree import get_directory_tree, get_path


# FIXME: exactly same function is in test_filemanager_plugin.py
def add_project_and_select_file(file_path, project=None) -> None:
    tree = get_directory_tree()
    tree.add_project(project or file_path.parent)

    while True:
        tree.update()
        tree.select_file(file_path)
        if get_path(tree.selection()[0]) == file_path:
            return
        tree.item(tree.selection()[0], open=True)
        tree.event_generate("<<TreeviewOpen>>")


@pytest.fixture
def git_repo(tmp_path):
    run = partial(subprocess.run, stdout=subprocess.DEVNULL, shell=True, check=True, cwd=tmp_path)
    run("git init")
    run("git config user.name foo")  # not --global, will stay inside test repo
    run("git config user.email foo@bar.baz")

    (tmp_path / "unstaged.txt").write_text("Committed changes")
    (tmp_path / "added.txt").write_text("Committed changes")
    (tmp_path / "committed.txt").write_text("Committed changes")
    run("git add .")
    run("git commit -m initial")

    (tmp_path / "unstaged.txt").write_text("Changes not staged for commit")
    (tmp_path / "added.txt").write_text("Added changes")
    run("git add added.txt")

    return tmp_path


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_working_on_new_file(tree, git_repo):
    (git_repo / "a.py").write_text("lol")

    add_project_and_select_file(git_repo / "a.py")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    tree.contextmenu.invoke("git add")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    tree.contextmenu.invoke("* (undo add)")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    tree.contextmenu.invoke("git add")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    (git_repo / "a.py").write_text("wat")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "normal"

    tree.contextmenu.invoke("git add")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_working_on_committed_file(tree, git_repo):
    file_path = git_repo / "committed.txt"

    add_project_and_select_file(file_path, project=git_repo)
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    file_path.write_text("new text")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "normal"

    tree.contextmenu.invoke("git add")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    tree.contextmenu.invoke("* (undo add)")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "normal"

    tree.contextmenu.invoke("git add")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    file_path.write_text("this is even newer text")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "normal"


def test_project_containing_different_statuses(tree, git_repo):
    tree.add_project(git_repo)
    [git_repo_id] = tree.get_children()
    tree.selection_set(git_repo_id)

    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "normal"
