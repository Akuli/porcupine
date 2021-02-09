import functools
import logging
import pathlib
import sys
import tkinter
import traceback
import webbrowser
from tkinter import filedialog
from typing import Callable, Iterator, Optional, Sequence, Tuple, cast

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

from porcupine import settings, tabs, utils
from porcupine._state import filedialog_kwargs, get_main_window, get_tab_manager, quit

log = logging.getLogger(__name__)


# Try this:
#
#    import tkinter
#
#    def handler(event):
#        print("got event")
#        return 'break'
#
#    root = tkinter.Tk()
#    root.event_add('<<Foo>>', '<Control-w>')
#    root.bind('<<Foo>>', handler)
#    root.bind_class('Text', '<<Foo>>', handler)
#    text = tkinter.Text()
#    text.pack()
#    root.mainloop()
#
# Now type something, select some text in the text widget and press
# Control-w. The text gets deleted (stupid default binding) and "got event"
# gets printed (the event handler). But if you put
#
#    text.bind('<<Foo>>', handler)
#
# before root.mainloop(), then it works, so that has to be done for every
# text widget.
def _generate_event(name: str, junk: object) -> Literal['break']:
    get_main_window().event_generate(name)
    return 'break'


def _fix_text_widget_bindings(event: 'tkinter.Event[tkinter.Misc]') -> None:
    for virtual_event in event.widget.event_info():
        if virtual_event.startswith('<<Menubar:') and not event.widget.bind(virtual_event):
            # When the keys are pressed, generate the event on the main
            # window so the menu callback will trigger.
            event.widget.bind(virtual_event, functools.partial(_generate_event, virtual_event), add=True)
            assert event.widget.bind(virtual_event)


def _init() -> None:
    log.debug("_init() starts")
    main_window = get_main_window()
    main_window.config(menu=tkinter.Menu(main_window, tearoff=False))
    main_window.bind('<<PluginsLoaded>>', (lambda event: update_keyboard_shortcuts()), add=True)
    main_window.bind_class('Text', '<FocusIn>', _fix_text_widget_bindings, add=True)
    _fill_menus_with_default_stuff()
    log.debug("_init() done")


_MENU_ITEM_TYPES_WITH_LABEL = {'command', 'checkbutton', 'radiobutton', 'cascade'}


def _find_item(menu: tkinter.Menu, label: str) -> Optional[int]:
    last_index = menu.index('end')
    if last_index is not None:   # menu not empty
        for index in range(last_index + 1):
            if menu.type(index) in _MENU_ITEM_TYPES_WITH_LABEL and menu.entrycget(index, 'label') == label:
                return index
    return None


def get_menu(path: Optional[str]) -> tkinter.Menu:
    """
    Find a menu widget, creating menus as necessary.

    For example, ``get_menu("Tools/Python")`` returns a submenu labelled
    *Python* from a menu named *Tools*. The *Tools* menu is created if it
    doesn't already exist.

    If *path* is ``None``, then the menubar itself is returned.
    """
    main_window = get_main_window()
    main_menu = cast(tkinter.Menu, main_window.nametowidget(main_window.cget('menu')))
    if path is None:
        return main_menu

    menu = main_menu
    for label in path.split('/'):
        submenu_index = _find_item(menu, label)
        if submenu_index is None:
            # Need to pass the menu as an explicit argument to tkinter.Menu.
            # Otherwise add_cascade() below tries to allocate a crazy amount of
            # memory and freezes everything when running tests (don't know why)
            submenu = tkinter.Menu(menu, tearoff=False)
            if menu == main_menu and menu.index('end') is not None:
                # adding something to non-empty main menu, don't add all the
                # way to end so that "Help" menu stays at very end
                last_index = menu.index("end")
                assert last_index is not None
                menu.insert_cascade(last_index, label=label, menu=submenu)
            else:
                menu.add_cascade(label=label, menu=submenu)
            menu = submenu

        else:
            menu = cast(tkinter.Menu, menu.nametowidget(menu.entrycget(submenu_index, 'menu')))

    return menu


def add_config_file_button(path: pathlib.Path) -> None:
    """
    Add a button to *Settings/Config Files* that opens a file in Porcupine when
    it's clicked.
    """
    get_menu("Settings/Config Files").add_command(
        label=path.name,
        command=(lambda: get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))),
    )


def _walk_menu_contents(
    menu: Optional[tkinter.Menu] = None,
    path_prefix: str = '',
) -> Iterator[Tuple[str, tkinter.Menu, int]]:

    if menu is None:
        menu = get_menu(None)

    last_index = menu.index('end')
    if last_index is not None:   # menu not empty
        for index in range(last_index + 1):
            if menu.type(index) == 'cascade':
                submenu = cast(tkinter.Menu, menu.nametowidget(menu.entrycget(index, 'menu')))
                new_prefix = path_prefix + menu.entrycget(index, 'label') + '/'
                yield from _walk_menu_contents(submenu, new_prefix)
            elif menu.type(index) in _MENU_ITEM_TYPES_WITH_LABEL:
                path = path_prefix + menu.entrycget(index, 'label')
                yield (path, menu, index)


def _menu_event_handler(menu: tkinter.Menu, index: int, junk: 'tkinter.Event[tkinter.Misc]') -> utils.BreakOrNone:
    menu.invoke(index)
    return 'break'


def update_keyboard_shortcuts() -> None:
    """
    This function does two things to the *New File* menu item in the *File*
    menu, and similarly to all other menu items in all menus:

        * Show *Ctrl+N* (or *⌘N* on Mac) next to *New File*.
        * Ensure that the menu item's callback runs when Ctrl+N (or Command+N) is pressed.

    This has to be called when menus or keyboard shortcuts have been modified.
    It's called automatically when a plugin has been set up.
    """
    main_window = get_main_window()
    for path, menu, index in _walk_menu_contents():
        event_name = f'<<Menubar:{path}>>'

        # show keyboard shortcuts in menus
        menu.entryconfig(index, accelerator=utils.get_keyboard_shortcut(event_name, menu=True))

        # trigger menu items when <<Menubar:Foo/Bar>> events are generated
        if not main_window.bind(event_name):
            # FIXME: what if menu item is inserted somewhere else than to end, and indexes change?
            command = functools.partial(_menu_event_handler, menu, index)
            main_window.bind(event_name, command, add=True)


def set_enabled_based_on_tab(path: str, callback: Callable[[Optional[tabs.Tab]], bool]) -> Callable[..., None]:
    """Use this for disabling menu items depending on the currently selected tab.

    When the selected :class:`~porcupine.tabs.Tab` changes, ``callback`` will
    be called with the selected tab as an argument, or ``None`` if there are
    no tabs. If the callback returns ``False``, then the menu item given by
    *path* is disabled (so that it looks grayed out and can't be clicked).

    The *path* works similarly to :func:`get_menu`, except that it refers to a
    menu item rather than a submenu. For example, ``"Tools/Python/Black"``
    means a menu item labelled *Black* in the *Tools/Python* menu.

    For example, this creates a menu item ``Foo/Bar`` and disables it whenever
    the currently selected tab is not a :class:`porcupine.tabs.FileTab`::

        from porcupine import menubar, tabs

        def do_something():
            ...

        def setup():
            menubar.get_menu("Foo").add_command(label="Bar", command=do_something)
            menubar.set_enabled_based_on_tab("Foo/Bar", (lambda tab: isinstance(tab, tabs.FileTab)))

    Sometimes you need to update the enabled-ness of a menu item for other
    reasons than changing the currently selected tab. To do that, call the
    callback that this function returns. It's always called when the selected
    tab changes, but you can call it at other times too. The returned callback
    ignores all arguments given to it, which makes using it with ``.bind()``
    easier.
    """
    def update_enabledness(*junk: object) -> None:
        tab = get_tab_manager().select()
        menu = get_menu(path.rsplit('/', 1)[0] if '/' in path else None)
        index = _find_item(menu, path.split('/')[-1])
        if index is None:
            raise LookupError(f"menu item {path!r} not found")
        menu.entryconfig(index, state=('normal' if callback(tab) else 'disabled'))

    update_enabledness()
    get_tab_manager().bind('<<NotebookTabChanged>>', update_enabledness, add=True)
    return update_enabledness


# TODO: pluginify?
def _fill_menus_with_default_stuff() -> None:
    # Make sure to get the order of menus right:
    #   File, Edit, <everything else>, Help
    get_menu("Help")   # handled specially in get_menu
    get_menu("File")
    get_menu("Edit")

    def new_file() -> None:
        get_tab_manager().add_tab(tabs.FileTab(get_tab_manager()))

    def open_files() -> None:
        paths: Sequence[str] = filedialog.askopenfilenames(**filedialog_kwargs)

        # tkinter returns '' if the user cancels, and i'm arfaid that python
        # devs might "fix" a future version to return None
        if not paths:
            return

        for path in map(pathlib.Path, paths):
            try:
                tab = tabs.FileTab.open_file(get_tab_manager(), path)
            except (UnicodeError, OSError) as e:
                log.exception(f"opening '{path}' failed")
                utils.errordialog(type(e).__name__, "Opening failed!", traceback.format_exc())
                continue

            get_tab_manager().add_tab(tab)

    def save_file(save_as: bool) -> None:
        tab = get_tab_manager().select()
        assert isinstance(tab, tabs.FileTab)
        if save_as:
            tab.save_as()
        else:
            tab.save()

    def close_selected_tab() -> None:
        tab = get_tab_manager().select()
        assert tab is not None
        if tab.can_be_closed():
            get_tab_manager().close_tab(tab)

    get_menu("File").add_command(label="New File", command=new_file)
    get_menu("File").add_command(label="Open", command=open_files)
    get_menu("File").add_command(label="Save", command=functools.partial(save_file, False))
    get_menu("File").add_command(label="Save As", command=functools.partial(save_file, True))
    get_menu("File").add_separator()
    get_menu("File").add_command(label="Close", command=close_selected_tab)
    get_menu("File").add_command(label="Quit", command=quit)

    set_enabled_based_on_tab("File/Save", (lambda tab: isinstance(tab, tabs.FileTab)))
    set_enabled_based_on_tab("File/Save As", (lambda tab: isinstance(tab, tabs.FileTab)))
    set_enabled_based_on_tab("File/Close", (lambda tab: tab is not None))
    set_enabled_based_on_tab("File/Quit", (lambda tab: tab is None))

    def change_font_size(how: Literal['bigger', 'smaller', 'reset']) -> None:
        if how == 'reset':
            settings.reset('font_size')
            return

        size = settings.get('font_size', int)
        if how == 'bigger':
            size += 1
        else:
            size -= 1
            if size < 3:
                return

        settings.set_('font_size', size)

    # trigger change_font_size() with mouse wheel from any text widget
    utils.bind_mouse_wheel('Text', (
        lambda updn: change_font_size('bigger' if updn == 'up' else 'smaller')
    ), prefixes=(utils.contmand() + '-'), add=True)

    get_menu("View").add_command(label="Bigger Font", command=functools.partial(change_font_size, 'bigger'))
    get_menu("View").add_command(label="Smaller Font", command=functools.partial(change_font_size, 'smaller'))
    get_menu("View").add_command(label="Reset Font Size", command=functools.partial(change_font_size, 'reset'))
    set_enabled_based_on_tab("View/Bigger Font", (lambda tab: tab is not None))
    set_enabled_based_on_tab("View/Smaller Font", (lambda tab: tab is not None))
    set_enabled_based_on_tab("View/Reset Font Size", (lambda tab: tab is not None))

    get_menu("Settings").add_command(label="Porcupine Settings", command=settings.show_dialog)

    def add_link(menu_path: str, label: str, url: str) -> None:
        get_menu(menu_path).add_command(label=label, command=(lambda: webbrowser.open(url)))

    # TODO: porcupine starring button
    # TODO: does ##learnpython IRC link still work?
    add_link("Help", "Porcupine Wiki", "https://github.com/Akuli/porcupine/wiki")
    add_link("Help", "Report a problem or request a feature", "https://github.com/Akuli/porcupine/issues/new")
    add_link("Help/Python", "Free help chat", "http://webchat.freenode.net/?channels=%23%23learnpython")
    add_link("Help/Python", "My Python tutorial", "https://github.com/Akuli/python-tutorial/blob/master/README.md")
    add_link("Help/Python", "Official documentation", "https://docs.python.org/")
