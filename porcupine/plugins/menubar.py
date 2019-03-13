import teek as tk

from porcupine import get_main_window, actions, utils


class MenuManager:

    def __init__(self):
        self.main_menu = tk.Menu()
        self._submenus = {}         # {(menu, label): submenu}
        self.get_menu("Help")       # see comments in get_menu()
        self._items = {}            # {path: MenuItem}

    def get_menu(self, path):
        current_menu = self.main_menu
        for label in path.split('/'):
            try:
                current_menu = self._submenus[(current_menu, label)]
            except KeyError:
                submenu = tk.Menu()
                submenu_item = tk.MenuItem(label, submenu)

                # make sure that the help menu is always last, like
                # in most other programs
                if current_menu is self.main_menu:
                    current_menu.insert(-1, submenu_item)
                else:
                    current_menu.append(submenu_item)

                self._submenus[(current_menu, label)] = submenu
                current_menu = submenu

        return current_menu

    def setup_action(self, action_path):
        action = actions.get_action(action_path)
        if '/' in action_path:
            menupath, menulabel = action_path.rsplit('/', 1)
            menu = self.get_menu(menupath)
        else:
            menulabel = action_path
            menu = self.main_menu

        kwargs = {}
        if action.binding is not None:
            kwargs['accelerator'] = utils.get_keyboard_shortcut(
                action.binding)

        if action.kind == 'command':
            item = tk.MenuItem(menulabel, action.callback, **kwargs)
        elif action.kind == 'yesno':
            item = tk.MenuItem(menulabel, action.var, **kwargs)
        else:
            assert action.kind == 'choice'

            # yes, each choice item gets a separate submenu
            submenu_content = [tk.MenuItem(choice, action.var, choice)
                               for choice in action.choices]
            item = tk.MenuItem(menulabel, submenu_content)

        menu.append(item)
        self._items[action_path] = item
        self.on_enable_disable(action_path)

    def on_new_action(self, event):
        self.setup_action(actions.get_action(event.data))

    def on_enable_disable(self, action_path):
        action = actions.get_action(action_path)
        self._items[action_path].config['state'] = (
            'normal' if action.enabled else 'disabled')


def setup():
    window = get_main_window()
    menubar = MenuManager()
    window.config['menu'] = menubar.main_menu

    window.bind(
        '<<NewAction>>',
        lambda event: menubar.setup_action(event.data(str)),
        event=True)
    for able in ['En', 'Dis']:
        window.bind('<<Action{}abled>>'.format(able),
                    lambda event: menubar.on_enable_disable(event.data(str)),
                    event=True)

    for action in actions.get_all_actions():
        menubar.setup_action(action.path)
