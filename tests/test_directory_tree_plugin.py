import pytest

from porcupine import get_paned_window, utils, tabs
from porcupine.plugins import directory_tree as plugin_module
from porcupine.plugins.directory_tree import DirectoryTree


@pytest.fixture
def tree():
    [tree] = [w for w in utils.get_children_recursively(get_paned_window()) if isinstance(w, DirectoryTree)]
    yield tree
    for child in tree.get_children(''):
        tree.delete(child)


def test_adding_nested_projects(tree, tmp_path):
    def get_paths():
        return [tree.get_path(project) for project in tree.get_children()]

    (tmp_path / 'a' / 'b').mkdir(parents=True)
    assert get_paths() == []
    tree.add_project(tmp_path / 'a')
    assert get_paths() == [tmp_path / 'a']
    tree.add_project(tmp_path / 'a' / 'b')
    assert get_paths() == [tmp_path / 'a']
    tree.add_project(tmp_path)
    assert get_paths() == [tmp_path]


def test_autoclose(tree, tmp_path, tabmanager, monkeypatch):
    def get_project_names():
        return [tree.get_path(project).name for project in tree.get_children()]

    (tmp_path / 'a').mkdir(parents=True)
    (tmp_path / 'b').mkdir(parents=True)
    (tmp_path / 'c').mkdir(parents=True)
    (tmp_path / 'a' / 'README').touch()
    (tmp_path / 'b' / 'README').touch()
    (tmp_path / 'c' / 'README').touch()
    a_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'a' / 'README')
    b_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'b' / 'README')
    c_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'c' / 'README')
    monkeypatch.setattr(plugin_module, 'PROJECT_AUTOCLOSE_COUNT', 2)

    assert get_project_names() == []

    tabmanager.add_tab(a_tab)
    assert get_project_names() == ['a']
    tabmanager.add_tab(b_tab)
    assert get_project_names() == ['a', 'b']
    tabmanager.add_tab(c_tab)
    assert get_project_names() == ['a', 'b', 'c']

    tabmanager.close_tab(b_tab)
    assert get_project_names() == ['a', 'c']
    tabmanager.close_tab(c_tab)
    assert get_project_names() == ['a', 'c']
    tabmanager.close_tab(a_tab)
    assert get_project_names() == ['a', 'c']
