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
        assert actions.get_action(action.name) is action
        assert action in all_actions.values()

    assert actions.get_action("nonexistent action") is None

    all_actions["garbage"] = "mean lean fighting machine"  # type: ignore
    assert (
        actions.get_action("garbage") is None
    ), "`all_actions` should be a copy, changes to it should not effect `_actions`"
