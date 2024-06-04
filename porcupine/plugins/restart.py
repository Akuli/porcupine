"""Save and restore opened tabs when Porcupine is restarted."""
import logging
import pickle
from pathlib import Path

from porcupine import add_quit_callback, dirs, get_tab_manager, settings
from porcupine.settings import global_settings

log = logging.getLogger(__name__)


# https://fileinfo.com/extension/pkl
def _get_state_file() -> Path:
    return dirs.cache_dir / "restart_state.pkl"


# If loading a file fails, a dialog is created and it should be themed as user wants
setup_after = ["sun_valley_theme"]


def quit_callback() -> bool:
    file_contents = []

    if global_settings.get("remember_tabs_on_restart", bool):
        selected_tab = get_tab_manager().select()
        for tab in get_tab_manager().tabs():
            state = tab.get_state()
            if state is not None:
                file_contents.append(
                    {"tab_type": type(tab), "tab_state": state, "selected": (tab == selected_tab)}
                )
    else:
        # Ask user to save changes in open tabs. They will soon be gone.
        for tab in get_tab_manager().tabs():
            if not tab.can_be_closed():
                return False

    with _get_state_file().open("wb") as file:
        pickle.dump(file_contents, file)
    return True


def setup() -> None:
    global_settings.add_option("remember_tabs_on_restart", default=True)
    settings.add_checkbutton(
        "remember_tabs_on_restart", text="Remember open tabs when Porcupine is closed and reopened"
    )

    # this must run even if loading tabs from states below fails
    add_quit_callback(quit_callback)

    try:
        with _get_state_file().open("rb") as file:
            file_contents = pickle.load(file)
    except FileNotFoundError:
        file_contents = []

    for state_dict in file_contents:
        if isinstance(state_dict, tuple):
            log.info(f"state file contains a tab saved by Porcupine 0.93.x or older: {state_dict}")
            tab_type, tab_state = state_dict
            state_dict = {"tab_type": tab_type, "tab_state": tab_state, "selected": True}

        tab = state_dict["tab_type"].from_state(get_tab_manager(), state_dict["tab_state"])
        if tab is not None:
            get_tab_manager().add_tab(tab, select=state_dict["selected"])
