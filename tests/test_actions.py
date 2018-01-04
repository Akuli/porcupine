import contextlib
import itertools
import tkinter

import pytest

from porcupine import actions, get_main_window, get_tab_manager, tabs, utils


_action_path_counter = itertools.count()


@pytest.fixture
def action_path():
    return 'Test/Blah' + str(next(_action_path_counter))


def test_errors(porcusession, action_path):
    actions.add_command('Test Blah Blah', print)   # should work without '/'
    with pytest.raises(ValueError):
        actions.add_command('/wat', print)
    with pytest.raises(ValueError):
        actions.add_command('wat/', print)
    with pytest.raises(TypeError):
        actions.add_command(action_path, print, filetype_names=['Python'],
                            tabtypes=[tabs.Tab])

    actions.add_command(action_path, print)
    with pytest.raises(RuntimeError):
        actions.add_command(action_path, print)   # exists already


@contextlib.contextmanager
def action_events():
    new_events = []
    enable_events = []
    disable_events = []

    window = get_main_window()
    tb = utils.temporary_bind    # pep8 line length
    with tb(window, '<<NewAction>>', new_events.append):
        with tb(window, '<<ActionEnabled>>', enable_events.append):
            with tb(window, '<<ActionDisabled>>', disable_events.append):
                yield (new_events, enable_events, disable_events)

    assert not new_events
    assert not enable_events
    assert not disable_events


def test_add_command_and_stuff(porcusession, action_path):
    root = get_main_window()
    callback_ran = False

    def callback():
        nonlocal callback_ran
        callback_ran = True

    with action_events() as (new_events, enable_events, disable_events):
        action = actions.add_command(action_path, callback, '<<Test>>')
        assert new_events.pop().data == action_path
        assert actions.get_action(action_path) is action
        assert action in actions.get_all_actions()

        assert action.path == action_path
        assert action.kind == 'command'
        assert action.binding == '<<Test>>'
        assert action.enabled
        assert action.callback is callback
        assert not hasattr(action, 'var')
        assert not hasattr(action, 'choices')
        assert (        # pep8: indents don't need to be 4 spaces here
         repr(action) == str(action) ==
         "<Action object '" + action_path + "': kind='command', enabled=True>")

        action.enabled = False
        assert disable_events.pop().data == action_path
        assert 'enabled=False' in repr(action)
        action.enabled = False
        assert not disable_events

        action.enabled = True
        assert enable_events.pop().data == action_path
        assert 'enabled=True' in repr(action)
        action.enabled = True
        assert not enable_events

        with pytest.raises(TypeError):
            action.enabled = 1

    action.enabled = False

    assert not callback_ran
    root.event_generate('<<Test>>')
    assert not callback_ran
    action.enabled = True
    root.event_generate('<<Test>>')
    assert callback_ran

    root.unbind('<<Test>>')


def test_add_yesno(porcusession, action_path):
    assert actions.add_yesno(action_path + '_', True).var.get()
    assert not actions.add_yesno(action_path + '__', False).var.get()
    with pytest.raises(TypeError):
        actions.add_yesno(action_path)      # needs default or var

    var = tkinter.BooleanVar()
    var.set(True)
    action = actions.add_yesno(action_path + '1', var=var)
    assert not hasattr(action, 'callback')
    assert action.var is var
    assert not hasattr(action, 'choices')

    # default and var: var should be set to the default
    assert var.get()
    assert actions.add_yesno(action_path + '2', False, var=var).var is var
    assert not var.get()

    with action_events() as (new_events, enable_events, disable_events):
        root = get_main_window()

        action = actions.add_yesno(action_path, True, '<<Test>>')
        assert new_events.pop().data == action_path
        assert action.var.get()
        root.event_generate('<<Test>>')
        assert not action.var.get()

        action.enabled = False
        assert disable_events.pop().data == action_path
        assert not action.var.get()
        root.event_generate('<<Test>>')
        assert not action.var.get()

        action.enabled = True
        assert enable_events.pop().data == action_path
        assert not action.var.get()
        root.event_generate('<<Test>>')
        assert action.var.get()

    root.unbind('<<Test>>')


def test_add_choice(porcusession, action_path):
    assert actions.add_choice(action_path + '_',
                              ['a', 'b', 'c']).var.get() == 'a'
    assert actions.add_choice(action_path + '__',
                              ['a', 'b', 'c'], 'b').var.get() == 'b'

    with pytest.raises(ValueError):
        actions.add_choice(action_path, ['a', 'b', 'c'], 'd')

    var = tkinter.StringVar()
    var.set('d')
    with pytest.raises(ValueError):
        actions.add_choice(action_path, ['a', 'b', 'c'], var=var)

    var.set('c')
    with pytest.raises(ValueError):
        actions.add_choice(action_path, ['a', 'b', 'c'], 'd', var=var)

    # default and var: var should be set to the default
    action = actions.add_choice(action_path, ['a', 'b', 'c', 'd'], 'b',
                                var=var)
    assert action.var is var
    assert var.get() == 'b'

    with pytest.warns(RuntimeWarning):
        var.set('wat wat')


class Tab1(tabs.Tab):
    pass


class Tab2(tabs.Tab):
    pass


def test_tabtypes(porcusession, tabmanager, action_path):
    tab1 = Tab1(tabmanager)
    tab2 = Tab2(tabmanager)

    action = actions.add_yesno(action_path, False, tabtypes=[Tab2])
    assert not action.enabled

    tabmanager.add_tab(tab1)
    tabmanager.update()
    assert tabmanager.current_tab is tab1
    assert not action.enabled

    tabmanager.add_tab(tab2)
    tabmanager.update()
    assert tabmanager.current_tab is tab2
    assert action.enabled

    action2 = actions.add_yesno(action_path + '2', True, tabtypes=[Tab2, None])
    assert action2.enabled

    tabmanager.close_tab(tab2)
    assert tabmanager.current_tab is tab1
    tabmanager.update()
    assert not action2.enabled

    tabmanager.close_tab(tab1)
    assert action2.enabled


#def test_filetype_names(porcusession, tabmanager, action_path, filetypes):
#    # make sure these filetypes exist
#    filetypes.get_filetype_by_name('C')
#    filetypes.get_filetype_by_name('Java')
#    filetypes.get_filetype_by_name('Python')
#    filetypes.get_filetype_by_name('DEFAULT')   # the plain text filetype
#
#    filetab = tabs.FileTab(tabmanager)
#    othertab = tabs.Tab(tabmanager)
#
#    action = actions.add_yesno(action_path, True,
#                               filetype_names=['C', 'Python'])
#    assert not action.enabled
#
#    tabmanager.add_tab(othertab)
#    assert not action.enabled
#    tabmanager.close_tab(othertab)
#    assert not action.enabled
#
#    tabmanager.add_tab(filetab)
#    assert not action.enabled
#    filetab.filetype = filetypes.get_filetype_by_name('Java')
#    assert not action.enabled
#    filetab.filetype = filetypes.get_filetype_by_name('C')
#    assert not action.enabled
#    filetab.filetype = 
