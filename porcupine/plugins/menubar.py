import tkinter

from porcupine import get_main_window, actions, utils


class MenubarHandler:

    def __init__(self):
        self.main_menu = tkinter.Menu(tearoff=False)
        self._submenus = {}         # {(menu, label): submenu}
        self.get_menu("Help")       # see comments in get_menu()
        self._items = {}            # {path: (menu, index)}

    def get_menu(self, path):
        current_menu = self.main_menu
        for label in path.split('/'):
            try:
                current_menu = self._submenus[(current_menu, label)]
            except KeyError:
                submenu = tkinter.Menu(tearoff=False)
                add_kwargs = {'label': label, 'menu': submenu}

                if (current_menu is self.main_menu and
                        current_menu.index('end') is not None):
                    # make sure that the help menu is always last, like
                    # in most other programs
                    before_last = current_menu.index('end')  # this is correct
                    current_menu.insert_cascade(before_last, **add_kwargs)
                else:
                    current_menu.add_cascade(**add_kwargs)

                self._submenus[(current_menu, label)] = submenu
                current_menu = submenu

        return current_menu

    def setup_action(self, action):
        if '/' in action.path:
            menupath, menulabel = action.path.rsplit('/', 1)
            menu = self.get_menu(menupath)
        else:
            menulabel = action.path
            menu = self.main_menu

        if action.kind in {'command', 'yesno'}:
            kwargs = {'label': menulabel}
            if action.binding is not None:
                kwargs['accelerator'] = utils.get_keyboard_shortcut(
                    action.binding)

            if action.kind == 'command':
                menu.add_command(command=action.callback, **kwargs)
            if action.kind == 'yesno':
                menu.add_checkbutton(variable=action.var, **kwargs)

        else:
            assert action.kind == 'choice'

            # yes, each choice item gets a separate submenu
            submenu = self.get_menu(action.path)
            for choice in action.choices:
                submenu.add_radiobutton(label=choice, variable=action.var)

        self._items[action.path] = (menu, menu.index('end'))
        self.on_enable_disable(action.path)

    def on_new_action(self, event):
        self.setup_action(actions.get_action(event.data))

    def on_enable_disable(self, action_path):
        action = actions.get_action(action_path)
        menu, index = self._items[action_path]
        menu.entryconfig(
            index, state=('normal' if action.enabled else 'disabled'))


def setup():
    window = get_main_window()
    menubar = MenubarHandler()
    window['menu'] = menubar.main_menu

    utils.bind_with_data(
        window, '<<NewAction>>', menubar.on_new_action, add=True)
    utils.bind_with_data(
        window, '<<ActionEnabled>>',
        (lambda event: menubar.on_enable_disable(event.data)), add=True)
    utils.bind_with_data(
        window, '<<ActionDisabled>>',
        (lambda event: menubar.on_enable_disable(event.data)), add=True)

    for action in actions.get_all_actions():
        menubar.setup_action(action)
