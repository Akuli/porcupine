import tkinter
from tkinter import ttk

from porcupine import get_main_window, pluginloader


def test_all_plugins_loaded_successfully(porcusession):
    # If loading failed, errors were logged and printed to stderr
    assert pluginloader.plugin_infos, "if this fails, it means no plugins got loaded"
    for info in pluginloader.plugin_infos:
        assert info.status == pluginloader.Status.ACTIVE


def get_children(widget):
    for child in widget.winfo_children():
        yield child
        yield from get_children(child)


def test_pluginmanager_plugin(porcusession, mocker):
    mocker.patch('tkinter.Toplevel.wait_window', autospec=True)
    get_main_window().event_generate('<<Menubar:Settings/Plugin Manager>>')
    tkinter.Toplevel.wait_window.assert_called_once()

    [dialog] = tkinter.Toplevel.wait_window.call_args[0]
    try:
        [treeview] = [widget for widget in get_children(dialog) if isinstance(widget, ttk.Treeview)]

        # Selecting the plugins runs code that finds description of plugin (as docstring)
        for info in pluginloader.plugin_infos:
            treeview.selection_set(info.name)
            treeview.update()
    finally:
        dialog.destroy()
