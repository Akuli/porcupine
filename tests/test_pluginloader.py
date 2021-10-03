from porcupine import pluginloader


def test_all_plugins_loaded_successfully():
    # If loading failed, errors were logged and printed to stderr
    assert pluginloader.plugin_infos, "if this fails, it means no plugins got loaded"
    for info in pluginloader.plugin_infos:
        # it's ok if you don't have tkdnd installed, doesn't get installed with pip
        if info.name != 'drop_to_open':
            assert info.status == pluginloader.Status.ACTIVE


# filetypes plugin adds custom command line arguments
def test_filetypes_plugin_cant_be_loaded_while_running():
    [info] = [info for info in pluginloader.plugin_infos if info.name == "filetypes"]
    assert not pluginloader.can_setup_while_running(info)


def test_setup_order_bugs(monkeypatch):
    [autoindent] = [i for i in pluginloader.plugin_infos if i.name == "autoindent"]
    [rstrip] = [i for i in pluginloader.plugin_infos if i.name == "rstrip"]

    assert autoindent.status == pluginloader.Status.ACTIVE
    assert rstrip.status == pluginloader.Status.ACTIVE

    with monkeypatch.context() as monkey:
        # can setup rstrip when autoindent is already active
        monkey.setattr(rstrip, "status", pluginloader.Status.DISABLED_BY_SETTINGS)
        assert pluginloader.can_setup_while_running(rstrip)

    with monkeypatch.context() as monkey:
        # but not the other way, autoindent must go first
        monkey.setattr(autoindent, "status", pluginloader.Status.DISABLED_BY_SETTINGS)
        assert not pluginloader.can_setup_while_running(autoindent)
