import pytest

from porcupine.plugins.directory_tree import get_path

# TODO: need more tests


@pytest.mark.parametrize("event", ["<<Cut>>", "<<Copy>>"])
def test_cutpasting_or_copypasting_to_same_dir(tree, tmp_path, mocker, event):
    mock = mocker.patch("porcupine.plugins.filemanager.ask_file_name")
    mock.return_value = tmp_path / "b"

    (tmp_path / "a").write_text("hello")
    tree.add_project(tmp_path)

    # Simulate user opening selected item
    tree.selection_set(tree.get_children()[0])
    tree.item(tree.get_children()[0], open=True)
    tree.event_generate("<<TreeviewOpen>>")
    tree.update()

    tree.select_file(tmp_path / "a")
    tree.event_generate(event)
    tree.event_generate("<<Paste>>")
    mock.assert_called_once_with(tmp_path / "a", is_paste=True, show_overwriting_option=False)

    if event == "<<Copy>>":
        assert (tmp_path / "a").read_text() == "hello"
    else:
        assert not (tmp_path / "a").exists()

    assert (tmp_path / "b").read_text() == "hello"
    assert get_path(tree.selection()[0]) == tmp_path / "b"
