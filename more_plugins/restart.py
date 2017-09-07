import pickle
import os

from porcupine import dirs, get_main_window, get_tab_manager

# TODO: figure out which file extension is best for pickled files
STATE_FILE = os.path.join(dirs.cachedir, 'state.pickle')


# TODO: add a nice API for doing this :(
def add_quit_callback(func):
    window = get_main_window()
    old_command = window.protocol('WM_DELETE_WINDOW')
    new_command = window.register(func) + '\n' + old_command
    window.protocol('WM_DELETE_WINDOW', new_command)


def save_states():
    states = []
    for tab in get_tab_manager().tabs:
        if hasattr(tab, 'get_state') and hasattr(type(tab), 'from_state'):
            states.append((type(tab), tab.get_state()))

    with open(STATE_FILE, 'wb') as file:
        pickle.dump(states, file)


def setup():
    # this must run even if loading tabs from states below fails
    add_quit_callback(save_states)

    try:
        with open(STATE_FILE, 'rb') as file:
            states = pickle.load(file)
    except FileNotFoundError:
        states = []

    # TODO: add a way to require this plugin to run after *all* other
    # plugins to the extent possible instead of delaying 500ms
    def tabs_from_state():
        for tab_class, state in states:
            tab = tab_class.from_state(get_tab_manager(), state)
            get_tab_manager().add_tab(tab)

    get_main_window().after(500, tabs_from_state)
