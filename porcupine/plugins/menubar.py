import tkinter
import typing

from porcupine import get_main_window, actions, utils


class MenuManager:

    def __init__(self) -> None:
        self.main_menu = tkinter.Menu(tearoff=False)
        self._submenus: typing.Dict[
            typing.Tuple[tkinter.Menu, str],    # (menu, label)
            tkinter.Menu,                       # submenu
        ] = {}
        self.get_menu("Help")       # see comments in get_menu()
        self._items: typing.Dict[
            str,                                # path, e.g. "File/Open"
            typing.Tuple[tkinter.Menu, int],    # (menu, index)
        ] = {}

    def get_menu(self, path: str) -> tkinter.Menu:
        current_menu = self.main_menu
        for label in path.split('/'):
            try:
                current_menu = self._submenus[(current_menu, label)]
            except KeyError:
                submenu = tkinter.Menu(tearoff=False)

                if (current_menu is self.main_menu and
                        current_menu.index('end') is not None):
                    # make sure that the help menu is always last, like
                    # in most other programs
                    before_last = current_menu.index('end')  # this works lol
                    assert before_last is not None
                    current_menu.insert_cascade(
                        before_last, label=label, menu=submenu)
                else:
                    current_menu.add_cascade(label=label, menu=submenu)

                self._submenus[(current_menu, label)] = submenu
                current_menu = submenu

        return current_menu

    def setup_action(self, action: actions.Action) -> None:
        if '/' in action.path:
            menupath, menulabel = action.path.rsplit('/', 1)
            menu = self.get_menu(menupath)
        else:
            menulabel = action.path
            menu = self.main_menu

        if action.kind in {'command', 'yesno'}:
            if action.binding is None:
                accel = ''
            else:
                accel = utils.get_keyboard_shortcut(action.binding)

            if action.kind == 'command':
                menu.add_command(
                    label=menulabel, accelerator=accel,
                    command=action.callback)
            if action.kind == 'yesno':
                assert isinstance(action.var, tkinter.BooleanVar)
                menu.add_checkbutton(
                    label=menulabel, accelerator=accel,
                    variable=action.var)

        else:
            assert action.kind == 'choice'

            # yes, each choice item gets a separate submenu
            submenu = self.get_menu(action.path)
            for choice in action.choices:
                assert isinstance(action.var, tkinter.StringVar)
                submenu.add_radiobutton(label=choice, variable=action.var)

        index = menu.index('end')
        assert index is not None
        if menu is self.main_menu:
            # yes, this is needed for the main menu, but not for submenus...
            # i have no idea why, and i don't care
            index -= 1

        self._items[action.path] = (menu, index)
        self.on_enable_disable(action.path)

    def on_new_action(self, event: utils.EventWithData) -> None:
        self.setup_action(actions.get_action(event.data_string))

    def on_enable_disable(self, action_path: str) -> None:
        action = actions.get_action(action_path)
        menu, index = self._items[action_path]
        menu.entryconfig(
            index, state=('normal' if action.enabled else 'disabled'))


def setup() -> None:
    window = get_main_window()
    menubar = MenuManager()
    window['menu'] = menubar.main_menu

    utils.bind_with_data(
        window, '<<NewAction>>', menubar.on_new_action, add=True)
    utils.bind_with_data(
        window, '<<ActionEnabled>>',
        (lambda event: menubar.on_enable_disable(event.data_string)), add=True)
    utils.bind_with_data(
        window, '<<ActionDisabled>>',
        (lambda event: menubar.on_enable_disable(event.data_string)), add=True)

    for action in actions.get_all_actions():
        menubar.setup_action(action)
