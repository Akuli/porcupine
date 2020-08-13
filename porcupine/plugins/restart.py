"""Save and restore Porcupine's state when Porcupine is restarted."""
# TODO: remember which tab was selected
import pickle
import pkgutil

from porcupine import dirs, get_main_window, get_tab_manager
from porcupine.plugins import __path__ as plugin_paths

# setup() must be called after setting up everything else
setup_after = [
    name for finder, name, ispkg in pkgutil.iter_modules(plugin_paths)
    if 'porcupine.plugins.' + name != __name__
]

# https://fileinfo.com/extension/pkl
STATE_FILE = dirs.cachedir / 'restart_state.pkl'


def save_states(junk: object) -> None:
    states = []
    for tab in get_tab_manager().tabs():
        state = tab.get_state()
        if state is not None:
            states.append((type(tab), state))

    with STATE_FILE.open('wb') as file:
        pickle.dump(states, file)


def setup() -> None:
    # this must run even if loading tabs from states below fails
    get_main_window().bind('<<PorcupineQuit>>', save_states, add=True)

    try:
        with STATE_FILE.open('rb') as file:
            states = pickle.load(file)
    except FileNotFoundError:
        states = []

    for tab_class, state in states:
        tab = tab_class.from_state(get_tab_manager(), state)
        get_tab_manager().add_tab(tab)
