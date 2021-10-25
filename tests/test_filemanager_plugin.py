import logging
import sys

import pytest

from porcupine.plugins.directory_tree import get_directory_tree, get_path
from porcupine.plugins.filemanager import FilenameMode


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
def check_error(caplog):
    def actually_check_error(title, text, error_string):
        from tkinter.messagebox import showerror  # a mock

        showerror.assert_called_once_with(title, text, detail=error_string)
        assert caplog.record_tuples == [("porcupine.plugins.filemanager", logging.ERROR, text)]

    return actually_check_error


@pytest.mark.parametrize("event", ["<<Cut>>", "<<Copy>>"])
def test_cutpasting_or_copypasting_to_same_dir(tree, tmp_path, mocker, event):
    ask_file_name = mocker.patch("porcupine.plugins.filemanager.ask_file_name")
    ask_file_name.return_value = tmp_path / "bar"

    (tmp_path / "foo").write_text("hello")
    add_project_and_select_file(tmp_path / "foo")

    tree.event_generate(event)
    tree.event_generate("<<Paste>>")
    ask_file_name.assert_called_once_with(tmp_path.parent, "foo", mode=FilenameMode.PASTE, can_overwrite=False)

    if event == "<<Copy>>":
        assert (tmp_path / "foo").read_text() == "hello"
    else:
        assert not (tmp_path / "foo").exists()

    assert (tmp_path / "bar").read_text() == "hello"
    assert get_path(tree.selection()[0]) == tmp_path / "bar"


@pytest.mark.parametrize("event", ["<<Cut>>", "<<Copy>>"])
def test_cutpasting_and_copypasting_error(tree, tmp_path, mocker, event, check_error):
    if event == "<<Copy>>":
        shutil_mock = mocker.patch("porcupine.plugins.filemanager.shutil").copy
        copy_or_move = "copy"
        copying_or_moving = "copying"
    else:
        shutil_mock = mocker.patch("porcupine.plugins.filemanager.shutil").move
        copy_or_move = "move"
        copying_or_moving = "moving"

    shutil_mock.side_effect = PermissionError("[Errno 13] Permission denied: '/dev/xyz'")

    mocker.patch("porcupine.plugins.filemanager.ask_file_name").return_value = tmp_path / "bar"
    mocker.patch("tkinter.messagebox.showerror")

    (tmp_path / "foo").write_text("hello")
    add_project_and_select_file(tmp_path / "foo")
    tree.event_generate(event)
    tree.event_generate("<<Paste>>")

    check_error(
        copying_or_moving.capitalize() + " failed",
        f"Cannot {copy_or_move} {tmp_path / 'foo'} to {tmp_path / 'bar'}.",
        "PermissionError: [Errno 13] Permission denied: '/dev/xyz'",
    )


def test_delete_error(tree, tmp_path, mocker, check_error):
    rmtree = mocker.patch("porcupine.plugins.filemanager.shutil").rmtree
    mocker.patch("tkinter.messagebox.showerror")
    askyesno = mocker.patch("tkinter.messagebox.askyesno")

    rmtree.side_effect = PermissionError("[Errno 13] Permission denied: '/dev/xyz'")
    askyesno.return_value = True

    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "bar").write_text("hello")
    add_project_and_select_file(tmp_path / "foo")
    tree.event_generate("<<FileManager:Delete>>")

    rmtree.assert_called_once_with(tmp_path / "foo")
    askyesno.assert_called_once_with(
        "Delete foo",
        "Do you want to permanently delete foo and everything inside it?",
        icon="warning",
    )
    check_error(
        "Deleting failed",
        f"Deleting {tmp_path / 'foo'} failed.",
        "PermissionError: [Errno 13] Permission denied: '/dev/xyz'",
    )


def test_trashing_error(tree, tmp_path, mocker, check_error):
    send2trash = mocker.patch("porcupine.plugins.filemanager.send2trash")
    mocker.patch("tkinter.messagebox.showerror")
    askyesno = mocker.patch("tkinter.messagebox.askyesno")

    send2trash.side_effect = RuntimeError("lol")
    askyesno.return_value = True

    (tmp_path / "foo").write_text("hello")
    add_project_and_select_file(tmp_path / "foo")
    tree.event_generate("<<FileManager:Trash>>")

    send2trash.assert_called_once_with(tmp_path / "foo")
    if sys.platform == "win32":
        askyesno.assert_called_once_with(
            "Move foo to recycle bin", "Do you want to move foo to recycle bin?", icon="warning"
        )
        check_error(
            "Can't move to recycle bin",
            f"Moving {tmp_path / 'foo'} to recycle bin failed.",
            "RuntimeError: lol",
        )
    else:
        askyesno.assert_called_once_with(
            "Move foo to trash", "Do you want to move foo to trash?", icon="warning"
        )
        check_error(
            "Can't move to trash",
            f"Moving {tmp_path / 'foo'} to trash failed.",
            "RuntimeError: lol",
        )


def test_copy_overwriting_opened_file(tabmanager, tree, tmp_path, mocker):
    mocker.patch("porcupine.plugins.filemanager.ask_file_name").return_value = tmp_path / "foo.txt"

    (tmp_path / "foo.txt").write_text("old foo")
    (tmp_path / "subfolder").mkdir()
    (tmp_path / "subfolder" / "foo.txt").write_text("new foo")

    tab = tabmanager.open_file(tmp_path / "foo.txt")

    add_project_and_select_file(tmp_path / "subfolder" / "foo.txt", project=tmp_path)
    tree.event_generate("<<Copy>>")
    add_project_and_select_file(tmp_path / "foo.txt", project=tmp_path)
    tree.event_generate("<<Paste>>")

    assert tab.textwidget.get("1.0", "end").strip() == "new foo"
