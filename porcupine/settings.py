import atexit
import codecs
import dataclasses
import functools
import itertools
import json
import logging
import pathlib
import tkinter.font
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Generic, IO, List, Optional, Tuple, TYPE_CHECKING, Type, TypeVar, Union, overload
import weakref

import porcupine
from porcupine import dirs, images, utils
from porcupine.filetypes import get_all_filetypes


_Val = TypeVar('_Val', str, int)


class _Option(Generic[_Val]):

    def __init__(self, name: str, default: _Val) -> None:
        self.name = name
        self.value: _Val = default
        self.default: _Val = default
        self.variables: 'weakref.WeakSet[tkinter.StringVar]' = weakref.WeakSet()

    def set(self, value: Union[str, int]) -> None:
        if not isinstance(value, type(self.default)):
            raise TypeError(f"expected {type(self.default).__name__}, got {type(value).__name__}")

        # don't create change events when nothing changes (helps avoid infinite recursion)
        if self.value == value:
            return
        self.value = value

        event_name = f'<<SettingsChanged:{self.name}>>'
        log.debug(f"{self.name} was set to {value!r}, generating {event_name} events")

        not_notified_yet: List[tkinter.Misc] = [porcupine.get_main_window()]
        while not_notified_yet:
            widget = not_notified_yet.pop()
            widget.event_generate(event_name)
            not_notified_yet.extend(widget.winfo_children())


log = logging.getLogger(__name__)
_FILE_PATH = dirs.configdir / 'settings.json'

# _json_file_contents may contain stuff that isn't in _options yet
_json_file_contents: Dict[str, Any] = {}
_options: Dict[str, Union[_Option[str], _Option[int]]] = {}


# add 'from builtins import set as builtin_set' if needed
def set(option_name: str, value: Union[str, int]) -> None:
    """Set the value of an opiton."""
    _options[option_name].set(value)


def get(option_name: str, tybe: Type[_Val]) -> _Val:
    """
    Return the current value of an option.
    *tybe* should be ``str`` or ``int`` depending on what type the option is.
    """
    result = _options[option_name].value
    if not isinstance(result, tybe):
        raise TypeError(f"use {type(result).__name__} instead of {tybe.__name__}")
    return result


def reset(option_name: str) -> None:
    """Set an option to its default value given to :func:`add_option`."""
    option = _options[option_name]
    option.set(option.default)


def reset_all() -> None:
    """
    Reset all settings, including the ones not shown in the setting dialog.
    Clicking the reset button of the setting dialog runs this function.
    """
    _json_file_contents.clear()
    for name in _options:
        reset(name)


def add_option(option_name: str, default: Union[str, int]) -> None:
    """
    Add a custom option.

    The type of *default* determines how :func:`set` and :func:`get` behave.
    For example, if *default* is a string, then
    calling :func:`set` with a value that isn't a string or
    calling :func:`get` with the type set to something else than ``str``
    is an error.
    """
    if option_name in _options:
        raise RuntimeError(f"there's already an option named {option_name!r}")

    # TODO: create mypy issues about need for Any-typing
    option: Any = _Option(option_name, default)
    _options[option_name] = option
    if option_name in _json_file_contents:
        # this errors if _json_file_contents has wrong type value
        # TODO: add test
        option.set(_json_file_contents[option_name])


def _load_from_file() -> None:
    assert not _options    # add_option() uses _json_file_contents
    try:
        with _FILE_PATH.open('r', encoding='utf-8') as file:
            _json_file_contents.update(json.load(file))
    except FileNotFoundError:
        pass


def save() -> None:
    """Save the settings to the config file.

    Note that :func:`porcupine.run` always calls this before it returns,
    so usually you don't need to worry about calling this yourself.
    """
    _json_file_contents.update({
        name: option.value
        for name, option in _options.items()
    })

    # don't store anything that doesn't differ from defaults
    # also don't wipe unknown stuff from config file
    for name in list(_json_file_contents.keys() & _options.keys()):
        if _json_file_contents[name] == _options[name].default:
            del _json_file_contents[name]

    with _FILE_PATH.open('w', encoding='utf-8') as file:
        json.dump(_json_file_contents, file)


def _create_notebook() -> ttk.Notebook:
    dialog = tkinter.Toplevel()
    dialog.withdraw()
    dialog.title("Porcupine Settings")
    dialog.protocol('WM_DELETE_WINDOW', dialog.withdraw)
    dialog.bind('<Escape>', lambda event: dialog.withdraw())
    dialog.geometry('500x350')

    def confirm_and_reset_all() -> None:
        if messagebox.askyesno("Reset Settings", "Are you sure you want to reset all settings?", parent=dialog):
            reset_all()

    big_frame = ttk.Frame(dialog)
    big_frame.pack(fill='both', expand=True)
    notebook = ttk.Notebook(big_frame)
    notebook.pack(fill='both', expand=True)
    ttk.Separator(big_frame).pack(fill='x')
    buttonframe = ttk.Frame(big_frame)
    buttonframe.pack(fill='x')

    ttk.Button(buttonframe, text="Reset all settings", command=confirm_and_reset_all).pack(side='right')
    ttk.Button(buttonframe, text="OK", command=dialog.withdraw).pack(side='right')

    return notebook


_notebook: Optional[ttk.Notebook] = None


def show_dialog() -> None:
    """Show the "Porcupine Settings" dialog.

    This function is called when the user opens the dialog from the menu.
    """
    dialog = get_notebook().winfo_toplevel()
    dialog.transient(porcupine.get_main_window())
    dialog.deiconify()


def get_notebook() -> ttk.Notebook:
    """Return the notebook widget in the setting dialog.

    Use ``settings.get_notebook().winfo_toplevel()`` to access the dialog
    itself. It's a :class:`tkinter.Toplevel`.
    """
    if _notebook is None:
        raise RuntimeError("porcupine isn't running")
    return _notebook


def _get_blank_triangle_sized_image(*, _cache: List[tkinter.PhotoImage] = []) -> tkinter.PhotoImage:
    # see images/__init__.py
    if not _cache:
        _cache.append(tkinter.PhotoImage(
            width=images.get('triangle').width(),
            height=images.get('triangle').height()))
        atexit.register(_cache.clear)
    return _cache[0]


def _create_validation_triangle(
    widget: ttk.Entry,
    option_name: str,
    tybe: Type[_Val],
    callback: Callable[[_Val], bool],
) -> ttk.Label:

    triangle = ttk.Label(widget.master)
    var = tkinter.StringVar()

    def var_changed(*junk: object) -> None:
        value_string = var.get()

        value: Optional[_Val]
        try:
            value = tybe(value_string)
        except ValueError:   # e.g. int('foo')
            value = None
        else:
            if not callback(value):
                value = None

        if value is None:
            triangle['image'] = images.get('triangle')
        else:
            triangle['image'] = _get_blank_triangle_sized_image()
            set(option_name, value)

    def setting_changed(junk: object = None) -> None:
        var.set(str(_options[option_name].value))

    widget.bind(f'<<SettingsChanged:{option_name}>>', setting_changed, add=True)
    var.trace_add('write', var_changed)
    setting_changed()

    widget['textvariable'] = var
    return triangle


def add_section(title_text: str) -> ttk.Frame:
    r"""Add a :class:`tkinter.ttk.Frame` to the notebook and return the frame.

    The columns of the frame's grid is configured suitably for
    :func:`add_entry`,
    :func:`add_combobox`,
    :func:`add_spinbox` and
    :func:`add_label`.
    Like this::


        ,-----------------------------------------------------------.
        | Porcupine Settings                                        |
        |-----------------------------------------------------------|
        |  / General \   / File Types \                             |
        |_/           \_____________________________________________|
        |                           :                           :   |
        |                           :                           :col|
        |         column 0          :         column 1          :umn|
        |                           :                           : 2 |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        |                           :                           :   |
        | ========================================================= |
        |                                   ,---------. ,---------. |
        |                                   |   OK    | |  Reset  | |
        |                                   `---------' `---------' |
        `-----------------------------------------------------------'

    Column 0 typically contains labels such as "Font Family:", and column 1
    contains widgets for changing the settings. Column 2 is used for displaying
    |triangle| when the user has chosen the setting badly.
    """
    result = ttk.Frame(get_notebook())
    result.grid_columnconfigure(0, weight=1)
    result.grid_columnconfigure(1, weight=1)
    get_notebook().add(result, text=title_text)
    return result


# Widget is needed for chooser.master and triangle.grid
def _grid_widgets(label_text: str, chooser: tkinter.Widget, triangle: Optional[tkinter.Widget]) -> None:
    label = ttk.Label(chooser.master, text=label_text)
    label.grid(column=0, sticky='w')
    chooser.grid(row=label.grid_info()['row'], column=1, sticky='we')
    if triangle is not None:
        triangle.grid(row=label.grid_info()['row'], column=2)


def add_entry(
    section: ttk.Frame,
    option_name: str,
    text: str,
    validate_callback: Callable[[str], bool],
    **entry_kwargs: Any,
) -> ttk.Entry:
    """Add a :class:`tkinter.ttk.Entry` to the setting dialog.

    A label that displays *text* will be added next to the entry.
    All ``**entry_kwargs`` go to :class:`tkinter.ttk.Entry`.

    When the user types something into the entry,
    *validate_callback* is called with the text of the entry as its only argument.
    If it returns ``True``, then the option given by *option_name*
    is set to the string that the user typed.
    Otherwise |triangle| is shown.
    """
    entry = ttk.Entry(section, **entry_kwargs)
    triangle = _create_validation_triangle(entry, option_name, str, validate_callback)
    _grid_widgets(text, entry, triangle)
    return entry


def add_combobox(
    section: ttk.Frame,
    option_name: str,
    text: str,
    **combobox_kwargs: Any,
) -> ttk.Combobox:
    """Add a :class:`tkinter.ttk.Combobox` to the setting dialog.

    All ``**combobox_kwargs`` go to :class:`tkinter.ttk.Combobox`.
    Usually you should pass at least ``values=list_of_strings``.

    The content of the combobox is checked whenever it changes.
    If it's in ``combobox['values']``
    (given with the ``values=list_of_strings`` keyword argument or changed
    later by configuring the returned combobox),
    then the option given by *option_name* is set to the combobox content.
    Otherwise |triangle| is shown.
    """
    combo = ttk.Combobox(section, **combobox_kwargs)
    triangle = _create_validation_triangle(
        combo, option_name, str,
        lambda value: value in combo['values'])
    _grid_widgets(text, combo, triangle)
    return combo


def add_spinbox(
    section: ttk.Frame,
    option_name: str,
    text: str,
    **spinbox_kwargs: Any,
) -> ttk.Spinbox:
    """Add a :class:`utils.Spinbox` to the setting dialog.

    All ``**spinbox_kwargs`` go to :class:`utils.Spinbox`.
    Usually you should pass at least ``from_=some_integer, to=another_integer``.

    The content of the spinbox is checked whenever it changes.
    If it's a valid integer between ``spinbox['from']`` and ``spinbox['to']`` (inclusive),
    then the option given by *option_name* is set to the :class:`int`.
    Otherwise |triangle| is shown.
    """
    spinbox = utils.Spinbox(section, **spinbox_kwargs)
    triangle = _create_validation_triangle(
        spinbox, option_name, int,
        lambda value: int(spinbox['from']) <= value <= int(spinbox['to']))
    _grid_widgets(text, spinbox, triangle)
    return spinbox


def add_label(section: ttk.Frame, text: str) -> ttk.Label:
    """Add text to the setting dialog.

    This is useful for explaining what some options do with more than a few words.
    The text is always as wide as the dialog is, even when the dialog is resized.
    """
    label = ttk.Label(section, text=text)
    label.grid(column=0, columnspan=3, sticky='we', pady=10)

    def wrap_on_resize(event: tkinter.Event) -> None:
        assert event.width != '??'
        label['wraplength'] = event.width

    section.bind('<Configure>', wrap_on_resize, add=True)
    return label


def _encoding_exists(name: str) -> bool:
    try:
        codecs.lookup(name)
        return True
    except LookupError:
        return False


def _edit_filetypes_config() -> None:
    # porcupine/tabs.py imports this file
    # these local imports feel so evil xD  MUHAHAHAA!!!
    from porcupine import tabs

    path = dirs.configdir / 'filetypes.ini'
    manager = porcupine.get_tab_manager()
    manager.add_tab(tabs.FileTab.open_file(manager, path))
    get_notebook().winfo_toplevel().withdraw()


def _fill_notebook_with_defaults() -> None:
    general = add_section("General")

    # sort, remove duplicates, remove weird fonts starting with @ on windows
    font_families = sorted({
        family for family in tkinter.font.families()
        if not family.startswith('@')
    })

    add_combobox(general, 'font_family', "Font family:", values=font_families)
    add_spinbox(general, 'font_size', "Font size:", from_=3, to=1000)
    add_entry(general, 'encoding', "File encoding:", _encoding_exists)

    filetypes = add_section('File Types')
    add_label(filetypes, (
        "Currently there's no GUI for changing filetype specific settings, "
        "but they're stored in filetypes.ini and you can edit it yourself."
    ))
    ttk.Button(
        filetypes, text="Edit filetypes.ini", command=_edit_filetypes_config,
    ).grid(row=1, column=0, columnspan=3, sticky='')

    add_label(filetypes, (
        "You can use the following option to choose which filetype "
        "Porcupine should use when you create a new file in Porcupine. You "
        "can change the filetype after creating the file by clicking "
        "Filetypes in the menu bar."))

    # filetypes aren't loaded yet when this is called, get_all_filetypes()
    # returns empty list
    filetypes.after_idle(lambda: add_combobox(
        filetypes, 'default_filetype', "Default filetype for new files:",
        values=sorted(ft.name for ft in get_all_filetypes())))


def _init() -> None:
    global _notebook
    if _notebook is not None:
        raise RuntimeError("can't call _init() twice")

    try:
        _load_from_file()
    except Exception:
        log.exception(f"reading {_FILE_PATH} failed")

    fixedfont = tkinter.font.Font(name='TkFixedFont', exists=True)
    if fixedfont['size'] < 0:
        # negative sizes have a special meaning in Tk, and i don't care much
        # about it for porcupine, using stupid hard-coded default instead
        fixedfont['size'] = 10

    # fixedfont['family'] is typically e.g. 'Monospace', that's not included in
    # tkinter.font.families() because it refers to another font family that is
    # in tkinter.font.families()
    add_option('font_family', fixedfont.actual('family'))
    add_option('font_size', fixedfont['size'])
    add_option('encoding', 'utf-8')    # TODO: file-specific encodings
    add_option('pygments_style', 'default')
    add_option('default_filetype', 'Plain Text')

    # keep TkFixedFont up to date with settings
    def update_fixedfont(event: Optional[tkinter.Event] = None) -> None:
        # toplevel widgets get notified from their children's events, don't want that here
        if event is None or event.widget == porcupine.get_main_window():
            fixedfont.config(family=get('font_family', str), size=get('font_size', int))

    porcupine.get_main_window().bind('<<SettingsChanged:font_family>>', update_fixedfont, add=True)
    porcupine.get_main_window().bind('<<SettingsChanged:font_size>>', update_fixedfont, add=True)
    update_fixedfont()
    _notebook = _create_notebook()
    _fill_notebook_with_defaults()
