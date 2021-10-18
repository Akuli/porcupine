import shutil
import subprocess

import pytest


# FIXME: copy/pasted from test_directory_tree_plugin.py
def open_as_if_user_clicked(tree, item):
    tree.selection_set(item)
    tree.item(item, open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_working_on_untracked_file(tree, tmp_path):
    subprocess.check_call("git init", cwd=tmp_path, shell=True)
    (tmp_path / "a.py").write_text("lol")

    tree.add_project(tmp_path)
    [project_id] = tree.get_children("")
    open_as_if_user_clicked(tree, project_id)
    tree.select_file(tmp_path / "a.py")

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
