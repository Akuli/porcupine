from porcupine import actions


def test_action_registry():
    bare_action = actions.register_bare_action(
        name="bare action", description="", callback=lambda: None
    )
    filetab_action = actions.register_filetab_action(
        name="filetab action", description="", callback=lambda tab: None
    )
    path_action = actions.register_path_action(
        name="path action", description="", callback=lambda path: None
    )

    assert isinstance(bare_action, actions.BareAction)
    assert isinstance(filetab_action, actions.FileTabAction)
    assert isinstance(path_action, actions.PathAction)

    all_actions = actions.get_all_actions()
    for action in [bare_action, filetab_action, path_action]:
        assert actions.query_actions(action.name) == action
        assert action in all_actions.values()

    assert actions.query_actions("nonexistent action") is None
