from functools import partial
import shutil
import subprocess

import pytest

from porcupine.plugins.directory_tree import get_directory_tree


def add_project_and_select_file(project_path, file_path):
    tree = get_directory_tree()
    tree.add_project(project_path)
    [project_id] = tree.get_children("")
    tree.selection_set(project_id)
    tree.item(project_id, open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()
    tree.select_file(file_path)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_working_on_new_file(tree, tmp_path):
    subprocess.check_call("git init -q", cwd=tmp_path, shell=True)
    (tmp_path / "a.py").write_text("lol")

    add_project_and_select_file(tmp_path, tmp_path / "a.py")
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

    (tmp_path / "a.py").write_text("wat")
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
def test_working_on_committed_file(tree, tmp_path):
    run = partial(subprocess.run, stdout=subprocess.DEVNULL, shell=True, check=True, cwd=tmp_path)
    run("git init")
    run("git config user.name foo")  # not --global, will stay inside test repo
    run("git config user.email foo@bar.baz")
    (tmp_path / "a.py").write_text("lol")
    run("git add a.py")
    run("git commit -m asdf")

    add_project_and_select_file(tmp_path, tmp_path / "a.py")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "disabled"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "disabled"

    (tmp_path / "a.py").write_text("lolwat new text")
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

    (tmp_path / "a.py").write_text("this is even newer text")
    tree._populate_contextmenu()
    assert tree.contextmenu.entrycget("git add", "state") == "normal"
    assert tree.contextmenu.entrycget("* (undo add)", "state") == "normal"
    assert tree.contextmenu.entrycget("* (discard non-added changes)", "state") == "normal"
