import tkinter

_menubar = None
_submenus = {}     # {(menu, label): submenu}


# there's no ttk.Menu and tkinter.Menu looks a little different :(
def init():
    global _menubar
    _menubar = tkinter.Menu()
    get_menu("Help")    # see comments in get_menu()


def get_menu(label_path):
    """Return a submenu from the menubar.

    The *label_path* should be a ``/``-separated string of menu labels;
    for example, ``'File/Stuff'`` is a Stuff submenu under the File
    menu. Submenus are created automatically as needed.

    The menubar itself is returned if *label_path* is None.
    """
    if _menubar is None:
        raise RuntimeError("%s.init() wasn't called" % __name__)

    if label_path is None:
        return _menubar

    current_menu = _menubar
    for label in label_path.split('/'):
        try:
            current_menu = _submenus[(current_menu, label)]
        except KeyError:
            submenu = tkinter.Menu(tearoff=False)
            add_kwargs = {'label': label, 'menu': submenu}

            if (current_menu is _menubar and
                    current_menu.index('end') is not None):
                # make sure that the help menu is always last, like in
                # most other programs
                before_last = current_menu.index('end')  # yes, we need this
                current_menu.insert_cascade(before_last, **add_kwargs)
            else:
                current_menu.add_cascade(**add_kwargs)

            _submenus[(current_menu, label)] = submenu
            current_menu = submenu

    return current_menu
