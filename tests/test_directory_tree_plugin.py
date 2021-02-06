import pathlib

import pytest

from porcupine import get_paned_window, utils
from porcupine.plugins.directory_tree import DirectoryTree


@pytest.fixture
def tree():
    [tree] = [w for w in utils.get_children_recursively(get_paned_window()) if isinstance(w, DirectoryTree)]
    return tree


def test_adding_nested_projects(tree, tmp_path):
    (tmp_path / 'a' / 'b').mkdir(parents=True)

    def get_projects():
        return [pathlib.Path(tree.item(item_id, 'values')[0]) for item_id in tree.get_children()]

    assert get_projects() == []
    tree.add_project(tmp_path / 'a')
    assert get_projects() == [tmp_path / 'a']
    tree.add_project(tmp_path / 'a' / 'b')
    assert get_projects() == [tmp_path / 'a']
    tree.add_project(tmp_path)
    assert get_projects() == [tmp_path]
