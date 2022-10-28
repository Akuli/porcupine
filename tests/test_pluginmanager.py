import pytest

from porcupine import pluginloader
from porcupine.pluginmanager import create_dialog


@pytest.fixture
def dialog_content(mocker):
    dialog, content = create_dialog()
    yield content
    dialog.destroy()


def test_select_one(dialog_content):
    # Selecting the plugins runs code that finds description of plugin (as docstring)
    for info in pluginloader.plugin_infos:
        dialog_content.treeview.selection_set(info.name)
        dialog_content.treeview.update()


def test_enable_disable_multiple(dialog_content):
    def get_states():
        return (
            str(dialog_content.enable_button["state"]),
            str(dialog_content.disable_button["state"]),
        )

    dialog_content.treeview.selection_set([info.name for info in pluginloader.plugin_infos[:5]])
    dialog_content.treeview.update()

    assert dialog_content.description.get("1.0", "end - 1 char") == "5 plugins selected."
    assert get_states() == ("disabled", "normal")
    dialog_content.disable_button.invoke()
    assert get_states() == ("normal", "disabled")

    # Select more plugins
    dialog_content.treeview.selection_set([info.name for info in pluginloader.plugin_infos[:7]])
    dialog_content.treeview.update()

    assert get_states() == ("normal", "normal")
    dialog_content.enable_button.invoke()
    assert get_states() == ("disabled", "normal")


