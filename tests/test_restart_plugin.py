import pytest

from porcupine.tabs import Tab
from porcupine.settings import global_settings
from porcupine import get_main_window, get_tab_manager, quit


@pytest.fixture
def dont_remember_tabs_on_restart():
    # default value is True, set to False temporarily for testing
    assert global_settings.get("remember_tabs_on_restart", bool)  
    global_settings.set("remember_tabs_on_restart", False)
    yield
    global_settings.set("remember_tabs_on_restart", True)


def test_quit_without_remember_tabs_on_restart(mocker, dont_remember_tabs_on_restart):
    doesnt_wanna_close = Tab(get_tab_manager())
    doesnt_wanna_close.can_be_closed = mocker.Mock()
    doesnt_wanna_close.can_be_closed.return_value = False
    get_tab_manager().add_tab(Tab(get_tab_manager()))
    get_tab_manager().add_tab(doesnt_wanna_close)
    get_tab_manager().add_tab(Tab(get_tab_manager()))

    assert len(get_tab_manager().tabs()) == 3

    quit()  # should do nothing, because one tab doesn't want to be closed
    assert len(get_tab_manager().tabs()) == 3
    doesnt_wanna_close.can_be_closed.assert_called_once_with()

    # Close the offending tab. Then quitting should be possible.
    get_tab_manager().close_tab(doesnt_wanna_close)
    assert len(get_tab_manager().tabs()) == 2

    # Prevent quit() from breaking the rest of tests
    mocked_destroy = mocker.patch("tkinter.Tk.destroy")
    quit()
    mocked_destroy.assert_called_once_with()
    assert len(get_tab_manager().tabs()) == 0


def test_quit_with_remember_tabs_on_restart(mocker):
    doesnt_wanna_close = Tab(get_tab_manager())
    doesnt_wanna_close.can_be_closed = mocker.Mock()
    doesnt_wanna_close.can_be_closed.return_value = False
    get_tab_manager().add_tab(Tab(get_tab_manager()))
    get_tab_manager().add_tab(doesnt_wanna_close)
    get_tab_manager().add_tab(Tab(get_tab_manager()))
    assert len(get_tab_manager().tabs()) == 3

    # Prevent quit() from breaking the rest of tests
    mocked_destroy = mocker.patch("tkinter.Tk.destroy")
    quit()
    mocked_destroy.assert_called_once_with()
    assert len(get_tab_manager().tabs()) == 0
