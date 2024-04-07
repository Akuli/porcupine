"""This file creates the menubar near the top of the Porcupine window.

Here is a simple example. You can run it by saving it as a `.py` file in the
`porcupine/plugins/` folder.

    from tkinter import messagebox
    from porcupine import menubar

    def hello():
        messagebox.showinfo("Hello", "Hello World!")

    def setup():
        menubar.get_menu("Run/Greetings").add_command(label="Hello World", command=hello)

This creates a new *Greetings* submenu to Porcupine's *Run* menu. Inside the
*Greetings* menu, there is a *Hello World* menu item that shows a popup message
when it is clicked.

The `/`-separated strings are called *menu paths*. They specify a menu and an
item inside that menu. Here are some details and gotchas about menu paths:

- Menus will be created when they don't already exist.
- Menu paths must be in ASCII, because they are used in virtual events names (see below).
- Use `//` to display an actual slash character in the menus.
- Menu stuff might get rewritten soon. See issue #1342.

Associating key presses with menu items is currently quite complicated, and IMO
much more complicated than it needs to be. Here's how associating `Ctrl+F` with
`Edit/Find and Replace` works:
- `porcupine/default_keybindings.tcl` runs when Porcupine starts, and it
  associates the physical event `<Control-f>` with the virtual event
  `<<Menubar:Edit/Find and Replace>>` using the `event add` Tcl command.
- The `porcupine.menubar` module binds to the virtual event
  `<<Menubar:Edit/Find and Replace>>`. This binding invokes the
  `Find and Replace` menu item from the `Edit` menu whenever the
  `<<Menubar:Edit/Find and Replace>>` virtual event is generated.
  Similar bindings are created automatically for all menu items.
- The `find` plugin adds a `Find and Replace` option to the `Edit` menu in the menubar.

And here's what happens when the user actually presses Ctrl+F:

1. User presses `Ctrl+F`.
2. Tk generates a `<Control-f>` event. Tk also considers this to be a
   `<<Menubar:Edit/Find and Replace>>` event because of the `event add`.
3. Tk calls the automatically created ``<<Menubar:Edit/Find and Replace>>`
   binding because the corresponding event was generated.
4. The binding invokes the `Edit/Find and Replace` menu item.
5. Because the menu item was invoked, it runs its command as if it was clicked.
   This command is a function defined in `porcupine/plugins/find.py`.
6. The `find` plugin does its thing.
"""

from __future__ import annotations

import logging
import re
import sys
import tkinter
import webbrowser
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from string import ascii_lowercase
from tkinter import filedialog
from typing import Any, Callable, Literal

from porcupine import actions, pluginmanager, settings, tabs, utils
from porcupine._state import get_main_window, get_tab_manager, quit
from porcupine.settings import global_settings

log = logging.getLogger(__name__)


# For some reason, binding <F4> on Windows also captures Alt+F4 presses.
# IMO applications shouldn't receive the window manager's special key bindings.
# Windows is weird...
def _event_is_windows_alt_f4(event: tkinter.Event[tkinter.Misc]) -> bool:
    return (
        sys.platform == "win32"
        and isinstance(event.state, int)
        and bool(event.state & 0x20000)  # Alt key is pressed
        and event.keysym == "F4"
    )


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
def _generate_event(name: str, event: tkinter.Event[tkinter.Misc]) -> Literal["break"]:
    if _event_is_windows_alt_f4(event):
        quit()
    else:
        log.debug(f"Generating event: {name}")
        get_main_window().event_generate(name)
    return "break"


def _fix_text_widget_bindings(event: tkinter.Event[tkinter.Misc]) -> None:
    for virtual_event in event.widget.event_info():
        if virtual_event.startswith("<<Menubar:") and not event.widget.bind(virtual_event):
            # When the keys are pressed, generate the event on the main
            # window so the menu callback will trigger.
            event.widget.bind(virtual_event, partial(_generate_event, virtual_event), add=True)
            assert event.widget.bind(virtual_event)


def _init() -> None:
    log.debug("_init() starts")
    main_window = get_main_window()
    main_window.config(menu=tkinter.Menu(main_window, tearoff=False))
    main_window.bind("<<PluginsLoaded>>", (lambda event: update_keyboard_shortcuts()), add=True)
    main_window.bind_class("Text", "<FocusIn>", _fix_text_widget_bindings, add=True)
    _fill_menus_with_default_stuff()
    log.debug("_init() done")


_MENU_ITEM_TYPES_WITH_LABEL = {"command", "checkbutton", "radiobutton", "cascade"}


def _find_item(menu: tkinter.Menu, label: str) -> int | None:
    last_index = menu.index("end")
    if last_index is not None:  # menu not empty
        for index in range(last_index + 1):
            if (
                menu.type(index) in _MENU_ITEM_TYPES_WITH_LABEL
                and menu.entrycget(index, "label") == label
            ):
                return index
    return None


# "//" means literal backslash, lol
def _join(parts: list[str]) -> str:
    return "/".join(part.replace("/", "//") for part in parts)


def _split(string: str) -> list[str]:
    if not string:
        return []
    return [part.replace("//", "/") for part in re.split(r"(?<!/)/(?!/)", string)]


def _split_parent(string: str) -> tuple[str, str]:
    *parent_parts, child = _split(string)
    return (_join(parent_parts), child)


def get_menu(path: str) -> tkinter.Menu:
    """
    Find a menu widget, creating menus as necessary.

    For example, ``get_menu("Tools/Python")`` returns a submenu labelled
    *Python* from a menu named *Tools*. The *Tools* menu is created if it
    doesn't already exist.

    If *path* is the empty string, then the menubar itself is returned.
    """

    main_window = get_main_window()
    main_menu: tkinter.Menu = main_window.nametowidget(main_window["menu"])

    menu = main_menu
    for label in _split(path):
        submenu_index = _find_item(menu, label)
        if submenu_index is None:
            # Need to pass the menu as an explicit argument to tkinter.Menu.
            # Otherwise add_cascade() below tries to allocate a crazy amount of
            # memory and freezes everything when running tests (don't know why)
            submenu = tkinter.Menu(menu, tearoff=False)
            if menu == main_menu and menu.index("end") is not None:
                # adding something to non-empty main menu, don't add all the
                # way to end so that "Help" menu stays at very end
                last_index = menu.index("end")
                assert last_index is not None
                menu.insert_cascade(last_index, label=label, menu=submenu)
            else:
                menu.add_cascade(label=label, menu=submenu)
            menu = submenu

        else:
            menu = menu.nametowidget(menu.entrycget(submenu_index, "menu"))

    return menu


def add_config_file_button(path: Path, *, menu: str = "Settings/Config Files") -> None:
    """
    Add a button to *Settings/Config Files* (or some other menu)
    that opens a file in Porcupine when it's clicked.
    """
    get_menu(menu).add_command(
        label=f"Edit {path.name}", command=(lambda: get_tab_manager().open_file(path))
    )


def _walk_menu_contents(
    menu: tkinter.Menu, path_prefix: list[str] = []
) -> Iterator[tuple[str, tkinter.Menu, int]]:
    last_index = menu.index("end")
    if last_index is not None:  # menu not empty
        for index in range(last_index + 1):
            if menu.type(index) == "cascade":
                submenu: tkinter.Menu = menu.nametowidget(menu.entrycget(index, "menu"))
                new_prefix = path_prefix + [menu.entrycget(index, "label")]
                yield from _walk_menu_contents(submenu, new_prefix)
            elif menu.type(index) in _MENU_ITEM_TYPES_WITH_LABEL:
                path = path_prefix + [menu.entrycget(index, "label")]
                yield (_join(path), menu, index)


def _menu_event_handler(menu: tkinter.Menu, index: int, event: tkinter.Event[tkinter.Misc]) -> str:
    if _event_is_windows_alt_f4(event):
        quit()
    else:
        menu.invoke(index)
    return "break"


def _update_keyboard_shortcuts_inside_submenus() -> None:
    main_window = get_main_window()
    for path, menu, index in _walk_menu_contents(get_menu("")):
        if menu.entrycget(index, "accelerator"):
            # Already done, or menu item uses some custom stuff e.g. run plugin
            continue

        event_name = f"<<Menubar:{path}>>"

        # show keyboard shortcuts in menus
        menu.entryconfig(index, accelerator=utils.get_binding(event_name, menu=True))

        # trigger menu items when <<Menubar:Foo/Bar>> events are generated
        if not main_window.bind(event_name):
            # FIXME: what if menu item is inserted somewhere else than to end, and indexes change?
            command = partial(_menu_event_handler, menu, index)
            main_window.bind(event_name, command, add=True)


# Make sure that alt+e opens edit menu
def _update_shortcuts_for_opening_submenus() -> None:
    used_letters = set()
    for virtual_event in get_main_window().event_info():
        for physical_event in get_main_window().event_info(virtual_event):
            match = re.fullmatch(r"<Alt-Key-([a-z])>", physical_event)
            if match is not None:
                used_letters.add(match.group(1))

    menu = get_menu("")
    last_index = menu.index("end")
    assert last_index is not None
    for submenu_index in range(last_index + 1):
        for letter_index, letter in enumerate(menu.entrycget(submenu_index, "label").lower()):
            if letter in ascii_lowercase and letter not in used_letters:
                menu.entryconfig(submenu_index, underline=letter_index)
                used_letters.add(letter)
                break
        else:
            menu.entryconfig(submenu_index, accelerator="")


def update_keyboard_shortcuts() -> None:
    """
    This function does several different things to each menu item. Here's what
    it does to the *Edit* menu and the *Find and Replace* menu item inside it:

        * Show *Ctrl+F* (or *⌘F* on Mac) next to *Find and Replace*.
        * Ensure that the menu item's callback runs when Ctrl+F (or Command+F) is pressed.
        * Allow the *Edit* menu to be accessed by pressing Alt+E.

    This has to be called when menus or keyboard shortcuts have been modified.
    It's called automatically when a plugin has been set up.
    """
    _update_keyboard_shortcuts_inside_submenus()
    _update_shortcuts_for_opening_submenus()


_menu_item_enabledness_callbacks: list[Callable[..., None]] = []


def _refresh_menu_item_enabledness() -> None:
    for callback in _menu_item_enabledness_callbacks:
        callback()


# TODO: create type for events
def register_enabledness_check_event(event: str) -> None:
    """Register an event which will cause all menu items to check if they are available"""
    get_tab_manager().bind(event, (lambda e: get_tab_manager().after_idle(_refresh_menu_item_enabledness)), add=True)


def set_enabled_based_on_tab(path: str, callback: Callable[[tabs.Tab | None], bool]) -> None:
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

    def update_enabledness(path: str) -> None:
        tab = get_tab_manager().select()

        parent, child = _split_parent(path)
        menu = get_menu(parent)
        index = _find_item(menu, child)
        if index is None:
            raise LookupError(f"menu item {path!r} not found")
        if callback(tab):
            menu.entryconfig(index, state="normal")
        else:
            menu.entryconfig(index, state="disabled")

    update_enabledness(path=path)

    _menu_item_enabledness_callbacks.append(partial(update_enabledness, path=path))


def get_filetab() -> tabs.FileTab:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    return tab


# FIXME(#1398): this function is deprecated
def add_filetab_command(path: str, func: Callable[[tabs.FileTab], object], **kwargs: Any) -> None:
    """
    This is a convenience function that does several things:

    * Create a menu item at the given path.
    * Ensure the menu item is enabled only when the selected tab is a
      :class:`~porcupine.tabs.FileTab`.
    * Run ``func`` when the menu item is clicked.

    The ``func`` is called with the selected tab as the only
    argument when the menu item is clicked. For example::

        from procupine import menubar, tabs

        def do_something(tab: tabs.FileTab) -> None:
            ...

        def setup() -> None:
            menubar.add_filetab_command("Edit/Do something", do_something)

    You usually don't need to provide any keyword arguments in ``**kwargs``,
    but if you do, they are passed to :meth:`tkinter.Menu.add_command`.
    """
    menu_path, item_text = _split_parent(path)
    get_menu(menu_path).add_command(label=item_text, command=lambda: func(get_filetab()), **kwargs)
    set_enabled_based_on_tab(path, (lambda tab: isinstance(tab, tabs.FileTab)))


def add_filetab_action(path: str, action: actions.FileTabAction, **kwargs: Any) -> None:
    """
    This is a convenience function that does several things:

    * Create a menu item at the given path with action.name as label
    * Ensure the menu item is enabled only when the selected tab is a
      :class:`~porcupine.tabs.FileTab` AND when
      :class:`~porcupine.actions.FileTabAction.availability_callback`
      returns True.
    * Run :class:`~porcupine.actions.FileTabAction.callback` when the
      menu item is clicked.

    The ``callback`` is called with the selected tab as the only
    argument when the menu item is clicked.

    You usually don't need to provide any keyword arguments in ``**kwargs``,
    but if you do, they are passed to :meth:`tkinter.Menu.add_command`.
    """

    get_menu(path).add_command(
        label=action.name, command=lambda: action.callback(get_filetab()), **kwargs
    )
    set_enabled_based_on_tab(
        path,
        callback=lambda tab: isinstance(tab, tabs.FileTab) and action.availability_callback(tab),
    )


# TODO: pluginify?
def _fill_menus_with_default_stuff() -> None:
    register_enabledness_check_event("<<NotebookTabChanged>>")

    # Make sure to get the order of menus right:
    #   File, Edit, <everything else>, Help
    get_menu("Help")  # handled specially in get_menu
    get_menu("File")
    get_menu("Edit")

    def new_file() -> None:
        get_tab_manager().add_tab(tabs.FileTab(get_tab_manager()))

    def open_files() -> None:
        # paths is "" or tuple
        paths = filedialog.askopenfilenames()
        for path in map(Path, paths):
            get_tab_manager().open_file(path)

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

    def focus_active_tab() -> None:
        tab = get_tab_manager().select()
        if tab is not None:
            tab.event_generate("<<TabSelected>>")

    get_menu("File").add_command(label="New File", command=new_file)
    get_menu("File").add_command(label="Open", command=open_files)
    get_menu("File").add_command(label="Save", command=partial(save_file, False))
    get_menu("File").add_command(label="Save As", command=partial(save_file, True))
    get_menu("File").add_separator()
    get_menu("File").add_command(label="Close", command=close_selected_tab)
    get_menu("File").add_command(label="Quit", command=quit)

    set_enabled_based_on_tab("File/Save", (lambda tab: isinstance(tab, tabs.FileTab)))
    set_enabled_based_on_tab("File/Save As", (lambda tab: isinstance(tab, tabs.FileTab)))
    set_enabled_based_on_tab("File/Close", (lambda tab: tab is not None))
    set_enabled_based_on_tab("File/Quit", (lambda tab: tab is None))

    def change_font_size(how: Literal["bigger", "smaller", "reset"]) -> None:
        if how == "reset":
            global_settings.reset("font_size")
            return

        size = global_settings.get("font_size", int)
        if how == "bigger":
            size += 1
        else:
            size -= 1
            if size < 3:
                return

        global_settings.set("font_size", size)

    get_menu("View").add_command(label="Bigger Font", command=partial(change_font_size, "bigger"))
    get_menu("View").add_command(label="Smaller Font", command=partial(change_font_size, "smaller"))
    get_menu("View").add_command(
        label="Reset Font Size", command=partial(change_font_size, "reset")
    )
    get_menu("View/Focus").add_command(label="Active file", command=focus_active_tab)
    set_enabled_based_on_tab("View/Focus/Active file", (lambda tab: tab is not None))
    set_enabled_based_on_tab("View/Bigger Font", (lambda tab: tab is not None))
    set_enabled_based_on_tab("View/Smaller Font", (lambda tab: tab is not None))
    set_enabled_based_on_tab("View/Reset Font Size", (lambda tab: tab is not None))

    get_menu("Settings").add_command(label="Porcupine Settings", command=settings.show_dialog)
    get_menu("Settings").add_command(label="Plugin Manager", command=pluginmanager.show_dialog)

    # TODO: these really belong to a plugin
    def add_link(menu_path: str, label: str, url: str) -> None:
        get_menu(menu_path).add_command(label=label, command=(lambda: webbrowser.open(url)))

    add_link("Help", "Create an issue on GitHub", "https://github.com/Akuli/porcupine/issues/new")
    add_link("Help", "User Documentation", "https://github.com/Akuli/porcupine/tree/main/user-doc")
