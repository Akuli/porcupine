"""Save and restore opened tabs when Porcupine is restarted."""
import logging
import pathlib
import pickle

from porcupine import dirs, get_main_window, get_tab_manager

log = logging.getLogger(__name__)

# https://fileinfo.com/extension/pkl
STATE_FILE = pathlib.Path(dirs.user_cache_dir) / "restart_state.pkl"


def save_states(junk: object) -> None:
    file_contents = []
    selected_tab = get_tab_manager().select()

    for tab in get_tab_manager().tabs():
        state = tab.get_state()
        if state is not None:
            file_contents.append(
                {"tab_type": type(tab), "tab_state": state, "selected": (tab == selected_tab)}
            )

    with STATE_FILE.open("wb") as file:
        pickle.dump(file_contents, file)


def setup() -> None:
    # this must run even if loading tabs from states below fails
    get_main_window().bind("<<PorcupineQuit>>", save_states, add=True)

    try:
        with STATE_FILE.open("rb") as file:
            file_contents = pickle.load(file)
    except FileNotFoundError:
        file_contents = []

    for state_dict in file_contents:
        if isinstance(state_dict, tuple):
            log.info(
                f"state file contains a tab saved by Porcupine 0.93.x or older: {state_dict}"
            )
            tab_type, tab_state = state_dict
            state_dict = {"tab_type": tab_type, "tab_state": tab_state, "selected": True}

        try:
            tab = state_dict["tab_type"].from_state(get_tab_manager(), state_dict["tab_state"])
        except FileNotFoundError:
            log.debug(
                f"file has been deleted, can't reopen tab: {state_dict}",
                exc_info=True,
            )
            continue

        get_tab_manager().add_tab(tab, select=state_dict["selected"])
