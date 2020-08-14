import atexit
import builtins
import copy
import dataclasses
import enum
from functools import partial
import json
import logging
import os
import pathlib
import tkinter.font
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, overload

import pygments.styles   # type: ignore

import porcupine
from porcupine import dirs, images, utils
from porcupine.filetypes import get_filetype_names


_log = logging.getLogger(__name__)


class LineEnding(enum.Enum):
    r"""
    This :mod:`enum` has these members representing different ways to write
    newline characters to files:

    .. data:: CR

        ``\r``, aka "Mac line endings".

    .. data:: LF

        ``\n``, aka "Linux/Unix line endings".

    .. data:: CRLF

        ``\r\n``, aka "Windows line endings".

    Python's :func:`open` function translates all of these to the string
    ``'\n'`` when reading files and uses a platform-specific default when
    writing files.

    There are 3 ways to represent line endings in Porcupine, and
    different things want the line ending represented in different ways:

        * The strings ``'\r'``, ``'\n'`` and ``'\r\n'``. For example,
          :func:`open` line endings are specified like this.
        * The strings ``'CR'``, ``'LF'`` and ``'CRLF'``. Line endings are
          typically defined this way in configuration files, such as
          `editorconfig <https://editorconfig.org/>`_ files.
        * This enum. I recommend using this to avoid typos.
          For example, ``LineEnding[some_string_from_user]`` (see below)
          raises an error if the string is invalid.

    Convert between this enum and the different kinds of strings like this:

        * Enum to backslashy string: ``LineEnding.CRLF.value == '\r\n'``
        * Enum to human readable string: ``LineEnding.CRLF.name == 'CRLF'``
        * Backslashy string to enum: ``LineEnding('\r\n') == LineEnding.CRLF``
        * Human readable string to enum: ``LineEnding['CRLF'] == LineEnding.CRLF``

    Use ``LineEnding(os.linesep)`` to get the platform-specific default.
    """
    CR = '\r'
    LF = '\n'
    CRLF = '\r\n'


def _type_check(tybe: type, obj: object) -> object:
    # dacite tricks needed for validating e.g. objects of type Optional[pathlib.Path]
    @dataclasses.dataclass
    class ValueContainer:
        value: tybe  # type: ignore

    return utils.dict_to_dataclass(ValueContainer, {'value': obj}).value


class _Option:

    def __init__(self, name: str, default: object, tybe: Any, converter: Callable[[Any], Any]) -> None:
        default = _type_check(tybe, default)
        self.name = name
        self.value = default
        self.default = default
        self.type = tybe
        self.converter = converter


def _get_json_path() -> pathlib.Path:
    return dirs.configdir / 'settings.json'


class Settings:

    def __init__(
            self,
            change_event_widget: Optional[tkinter.Misc],
            change_event_format: str):
        # '<<Foo:{}>>'
        assert '{}' in change_event_format
        assert change_event_format.startswith('<<')
        assert change_event_format.endswith('>>')

        self._options: Dict[str, _Option] = {}
        self._unknown_options: Dict[str, Any] = {}
        self._change_event_widget = change_event_widget  # None to notify all widgets
        self._change_event_format = change_event_format

    def add_option(
        self,
        option_name: str,
        default: Any,
        *,
        type: Optional[Any] = None,
        converter: Callable[[Any], Any] = (lambda x: x),
    ) -> None:
        """Add a custom option.

        The type of *default* determines how :func:`set` and :func:`get` behave.
        For example, if *default* is a string, then
        calling :func:`set` with a value that isn't a string or
        calling :func:`get` with the type set to something else than ``str``
        is an error. You can also provide a custom type with the *type*
        argument, e.g. ``add_option('foo', None, Optional[pathlib.Path])``.

        If you are adding a global option (see :class:`Settings` for non-global
        options), use only JSON-safe types. Let me know if this limitation is
        too annoying.

        If you are **not** adding a global option, you
        can also specify a *converter* that takes the value in the
        configuration file as an argument and returns an instance of *type*.
        For example, ``pygments_lexer`` is set to a string like
        "pygments.lexers.Foo" in the config file, even though it appears as a
        class in the settings object. That's implemented similarly to this::

            def import_lexer_class(name: str) -> something:
                ...

            filetab.settings.add_option(
                'pygments_lexer',
                pygments.lexers.TextLexer,
                ...
                converter=import_lexer_class)

        By default, the converter returns its argument unchanged.
        """
        if option_name in self._options:
            raise RuntimeError(f"there's already an option named {option_name!r}")

        if type is None:
            # using type as variable name, wanna access built-in named 'type'
            type = builtins.type(default)
        assert type is not None

        option = _Option(option_name, default, type, converter)
        self._options[option_name] = option

        try:
            value = self._unknown_options.pop(option_name)
        except KeyError:
            pass   # nothing relevant in config file, use default
        else:
            # Error handling here because it's not possible to fail early when
            # an option goes to _unknown_options, and bad data in a config file
            # shouldn't cause add_option() and the rest of a plugin's setup()
            # to fail.
            try:
                self.set(option_name, converter(value))
            except Exception:
                # can be an error from converter
                _log.exception(f"setting {option_name!r} to {value!r} failed")

    def set(self, option_name: str, value: object, *, from_config: bool = False) -> None:
        """Set the value of an opiton.

        Set ``from_config=True`` if the value comes from a configuration
        file (see :func:`add_option`). That does two things:

            * The converter given to :func:`add_option` will be used.
            * If the option hasn't been added with :func:`add_option` yet, then
              the value won't be set immediatelly, but instead it gets set
              later when the option is added.
        """
        if option_name not in self._options and from_config:
            self._unknown_options[option_name] = value
            return

        option = self._options[option_name]
        if from_config:
            value = option.converter(value)
        value = _type_check(option.type, value)

        # don't create change events when nothing changes (helps avoid infinite recursion)
        if option.value == value:
            return
        option.value = value

        event_name = self._change_event_format.format(option_name)
        _log.debug(f"{option_name} was set to {value!r}, generating {event_name} events")

        if self._change_event_widget is None:
            not_notified_yet: List[tkinter.Misc] = [porcupine.get_main_window()]
            while not_notified_yet:
                widget = not_notified_yet.pop()
                widget.event_generate(event_name)
                not_notified_yet.extend(widget.winfo_children())
        else:
            self._change_event_widget.event_generate(event_name)

    # I don't like how this requires overloads for every type
    # https://stackoverflow.com/q/61471700
    @overload
    def get(self, option_name: str, type: Type[pathlib.Path]) -> pathlib.Path: ...  # noqa
    @overload
    def get(self, option_name: str, type: Type[LineEnding]) -> LineEnding: ...  # noqa
    @overload
    def get(self, option_name: str, type: Type[str]) -> str: ...  # noqa
    @overload
    def get(self, option_name: str, type: Type[int]) -> int: ...  # noqa
    @overload
    def get(self, option_name: str, type: object) -> Any: ...  # noqa

    def get(self, option_name: str, type: Any) -> Any:
        """
        Return the current value of an option.
        *type* should be ``str`` or ``int`` depending on what type the option is.
        You can also specify ``object`` to allow any type.

        This method works correctly for :class:`str` and :class:`int`,
        but sometimes it returns Any because mypy sucks::

            foo = settings.get('something', str)
            reveal_type(foo)  # str

            shitty_bar = settings.get('something', Optional[pathlib.Path])
            reveal_type(shitty_bar)  # Any

        Use a type annotation to work around this (and make sure to write the
        same type two times)::

            good_bar: Optional[pathlib.Path] = settings.get('something', Optional[pathlib.Path])
            reveal_type(good_bar)  # Optional[pathlib.Path]

        Options of mutable types are returned as copies, so things like
        ``settings.get('something', List[str])`` always return a new list.
        If you want to change a setting like that, you need to first get a copy
        of the current value, then modify the copy, and finally :func:`set` it
        back. This is an easy way to make sure that change events run every
        time the value changes.
        """
        result = self._options[option_name].value
        result = _type_check(type, result)
        return copy.deepcopy(result)  # mutating wouldn't trigger change events

    def debug_dump(self) -> None:
        """Print all settings and their values. This is useful for debugging."""
        print(f"{len(self._options)} known options (add_option called)")
        for name, option in self._options.items():
            print(f'  {name} = {option.value!r}    (type: {option.type!r})')
        print()

        print(f"{len(self._unknown_options)} unknown options (add_option not called)")
        for name, value in self._unknown_options.items():
            print(f'  {name} = {value!r}')
        print()


_global_settings = Settings(None, '<<SettingChanged:{}>>')
add_option = _global_settings.add_option
set = _global_settings.set     # shadows the built-in set data structure
get = _global_settings.get
debug_dump = _global_settings.debug_dump


def reset(option_name: str) -> None:
    """Set an option to its default value given to :func:`add_option`."""
    set(option_name, _global_settings._options[option_name].default)


def reset_all() -> None:
    """
    Reset all settings, including the ones not shown in the setting dialog.
    Clicking the reset button of the setting dialog runs this function.
    """
    _global_settings._unknown_options.clear()
    for name in _global_settings._options:
        reset(name)


def _value_to_save(obj: object) -> object:
    # Enum options are stored as name strings, e.g. 'CRLF' for LineEnding.CRLF
    if isinstance(obj, enum.Enum):
        return obj.name
    return obj


def save() -> None:
    """Save the settings to the config file.

    Note that :func:`porcupine.run` always calls this before it returns,
    so usually you don't need to worry about calling this yourself.
    """
    currently_known_defaults = {
        name: opt.default
        for name, opt in _global_settings._options.items()
    }

    writing: Dict[str, Any] = _global_settings._unknown_options.copy()

    # don't wipe unknown stuff from config file
    writing.update({
        name: get(name, object)
        for name in currently_known_defaults.keys()
    })

    # don't store anything that doesn't differ from defaults
    for name, default in currently_known_defaults.items():
        if name in writing and writing[name] == default:
            del writing[name]

    with _get_json_path().open('w', encoding='utf-8') as file:
        json.dump({
            name: _value_to_save(value)
            for name, value in writing.items()
        }, file)


def _load_from_file() -> None:
    try:
        with _get_json_path().open('r', encoding='utf-8') as file:
            options = json.load(file)
    except FileNotFoundError:
        return

    for name, value in options.items():
        set(name, value, from_config=True)


# pygments styles can be uninstalled, must not end up with invalid pygments style that way
def _check_pygments_style(name: str) -> str:
    pygments.styles.get_style_by_name(name)   # may raise error that will get logged
    return name


def _init_global_settings() -> None:
    try:
        _load_from_file()
    except Exception:
        _log.exception(f"reading {_get_json_path()} failed")

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
    add_option('pygments_style', 'default', converter=_check_pygments_style)
    add_option('default_filetype', 'Python')
    add_option('disabled_plugins', [], type=List[str])
    add_option('default_line_ending', LineEnding(os.linesep), converter=LineEnding.__getitem__)

    # keep TkFixedFont up to date with settings
    def update_fixedfont(event: Optional[tkinter.Event]) -> None:
        # can't bind to get_tab_manager() as recommended in docs because tab
        # manager isn't ready yet when settings get inited
        if event is None or event.widget == porcupine.get_main_window():
            fixedfont.config(family=get('font_family', str), size=get('font_size', int))

    porcupine.get_main_window().bind('<<SettingChanged:font_family>>', update_fixedfont, add=True)
    porcupine.get_main_window().bind('<<SettingChanged:font_size>>', update_fixedfont, add=True)
    update_fixedfont(None)


def _create_notebook() -> ttk.Notebook:
    dialog = tkinter.Toplevel()
    dialog.withdraw()
    dialog.title("Porcupine Settings")
    dialog.protocol('WM_DELETE_WINDOW', dialog.withdraw)
    dialog.bind('<Escape>', (lambda event: dialog.withdraw()), add=True)
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


_StrOrInt = TypeVar('_StrOrInt', str, int)


def _create_validation_triangle(
    widget: ttk.Entry,
    option_name: str,
    tybe: Type[_StrOrInt],
    callback: Callable[[_StrOrInt], bool],
) -> ttk.Label:

    triangle = ttk.Label(widget.master)
    var = tkinter.StringVar()

    def var_changed(*junk: object) -> None:
        value_string = var.get()

        value: Optional[_StrOrInt]
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
            set(option_name, value, from_config=True)

    def setting_changed(junk: object = None) -> None:
        var.set(str(_value_to_save(get(option_name, object))))

    widget.bind(f'<<SettingChanged:{option_name}>>', setting_changed, add=True)
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
        |  / General \   / Config Files \                           |
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
    later by configuring the returned combobox), then the option given by
    *option_name* is set to the content of the combobox. The converter passed
    to :func:`add_option` will be used. If the content of the combobox is not
    in ``combobox['values']``, then |triangle| is shown.
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
) -> utils.Spinbox:
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


def _edit_file(path: pathlib.Path) -> None:
    # porcupine/tabs.py imports this file
    # these local imports feel so evil xD  MUHAHAHAA!!!
    from porcupine import tabs

    manager = porcupine.get_tab_manager()
    manager.add_tab(tabs.FileTab.open_file(manager, path))
    get_notebook().winfo_toplevel().withdraw()


def add_config_file_button(section: ttk.Frame, path: pathlib.Path) -> ttk.Button:
    """
    Add a button that opens a file in Porcupine when it's clicked.
    The button doesn't have any text next to it.
    """
    button = ttk.Button(section, text=f"Edit {path.name}", command=partial(_edit_file, path))
    button.grid(column=0, columnspan=3, sticky='', pady=5)
    return button


def _fill_notebook_with_defaults() -> None:
    general = add_section("General")

    # sort, remove duplicates, remove weird fonts starting with @ on windows
    font_families = sorted({
        family for family in tkinter.font.families()
        if not family.startswith('@')
    })

    add_combobox(general, 'font_family', "Font family:", values=font_families)
    add_spinbox(general, 'font_size', "Font size:", from_=3, to=1000)
    add_combobox(
        general, 'default_line_ending', "Default line ending:",
        values=[ending.name for ending in LineEnding])

    # filetypes aren't loaded yet when this is called
    general.after_idle(lambda: add_combobox(
        general, 'default_filetype', "Default filetype for new files:",
        values=sorted(get_filetype_names(), key=str.casefold),
    ))

    configs = add_section('Config Files')
    add_label(configs, (
        "Currently there's no GUI for changing these settings, but you can edit it the "
        "configuration files yourself."
    ))
    add_config_file_button(configs, dirs.configdir / 'filetypes.toml')


def _init() -> None:
    global _notebook
    if _notebook is not None:
        raise RuntimeError("can't call _init() twice")

    _init_global_settings()
    _notebook = _create_notebook()
    _fill_notebook_with_defaults()
