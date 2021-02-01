from porcupine import pluginloader


def test_all_plugins_loaded_successfully():
    # If loading failed, errors were logged and printed to stderr
    assert pluginloader.plugin_infos, "if this fails, it means no plugins got loaded"
    for info in pluginloader.plugin_infos:
        assert info.status == pluginloader.Status.ACTIVE
