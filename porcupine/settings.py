from __future__ import annotations

import atexit
import builtins
import contextlib
import copy
import dataclasses
import enum
import json
import logging
import os
import sys
import time
import tkinter
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Generator, Iterator, List, TypeVar, overload

import dacite
from pygments import styles, token

import porcupine
from porcupine import dirs, images, utils

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
    CR = "\r"
    LF = "\n"
    CRLF = "\r\n"


def _type_check(type_: object, obj: object) -> object:
    # dacite tricks needed for validating e.g. objects of type Optional[Path]
    @dataclasses.dataclass
    class ValueContainer:
        __annotations__ = {"value": type_}

    parsed = dacite.from_dict(ValueContainer, {"value": obj})
    return parsed.value  # type: ignore


class _Option:
    def __init__(
        self, name: str, default: object, type_: Any, converter: Callable[[Any], Any]
    ) -> None:
        default = _type_check(type_, default)
        self.name = name
        self.value = default
        self.default = default
        self.type = type_
        self.converter = converter
        self.tag: str | None = None


@dataclasses.dataclass
class _UnknownOption:
    value: Any
    call_converter: bool
    tag: str | None


def _default_converter(value: Any) -> Any:
    return value


# includes the parent
def _get_children_recursively(parent: tkinter.Misc) -> Iterator[tkinter.Misc]:
    yield parent
    for child in parent.winfo_children():
        yield from _get_children_recursively(child)


class Settings:
    def __init__(self, change_event_widget: tkinter.Misc | None, change_event_format: str):
        # '<<Foo:{}>>'
        assert "{}" in change_event_format
        assert change_event_format.startswith("<<")
        assert change_event_format.endswith(">>")

        self._options: dict[str, _Option] = {}
        self._unknown_options: dict[str, _UnknownOption] = {}
        self._change_event_widget = change_event_widget  # None to notify all widgets
        self._change_event_format = change_event_format
        self._pending_change_events: dict[str, tuple[object, object]] | None = None

    def add_option(
        self,
        option_name: str,
        default: Any,
        type_: Any | None = None,
        *,
        converter: Callable[[Any], Any] = _default_converter,
        exist_ok: bool = False,
    ) -> None:
        """Add a custom option.

        The type of *default* determines how :meth:`set` and :meth:`get` behave.
        For example, if *default* is a string, then
        calling :meth:`set` with a value that isn't a string or
        calling :meth:`get` with the type set to something else than ``str``
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
        Do not use a lambda function as the converter,
        because the settings must be picklable.

        If an option with the same name exists already, an error is raised by
        default, but if ``exist_ok=True`` is given, then adding the same
        option again is allowed. When this happens, an error is raised if
        *default*, *type* or *converter* doesn't match what was passed in when
        the option was added for the first time.
        """
        if type_ is None:
            type_ = type(default)
        assert type_ is not None

        if option_name in self._options:
            if not exist_ok:
                raise RuntimeError(f"there's already an option named {option_name!r}")
            old_option = self._options[option_name]
            assert default == old_option.default
            assert type_ == old_option.type
            assert converter == old_option.converter
            return

        option = _Option(option_name, default, type_, converter)
        self._options[option_name] = option

        try:
            unknown = self._unknown_options.pop(option_name)
        except KeyError:
            pass  # nothing relevant in config file, use default
        else:
            # Error handling here because it's not possible to fail early when
            # an option goes to _unknown_options, and bad data in a config file
            # shouldn't cause add_option() and the rest of a plugin's setup()
            # to fail.
            try:
                if unknown.call_converter:
                    self.set(option_name, converter(unknown.value), tag=unknown.tag)
                else:
                    self.set(option_name, unknown.value, tag=unknown.tag)
            except Exception:
                # can be an error from converter
                _log.exception(f"setting {option_name!r} to {unknown.value!r} failed")

    def _generate_change_event(
        self, option_name: str, old_value: object, new_value: object
    ) -> None:
        event_name = self._change_event_format.format(option_name)
        if old_value == new_value:
            _log.debug(f"not generating a change event because value didn't change: {event_name}")
            return

        _log.info(f"generating change event: {event_name}")

        if self._change_event_widget is None:
            try:
                main_window = porcupine.get_main_window()
            except RuntimeError as e:
                # on porcupine startup, plugin disable list needs to be set before main window exists
                if option_name != "disabled_plugins":
                    raise e
            else:
                for widget in _get_children_recursively(main_window):
                    widget.event_generate(event_name)
        else:
            self._change_event_widget.event_generate(event_name)

    # TODO: document this
    @contextlib.contextmanager
    def defer_change_events(self) -> Generator[None, None, None]:
        if self._pending_change_events is not None:
            raise RuntimeError("calls to defer_change_events() cannot be nested")

        self._pending_change_events = {}
        try:
            yield
        finally:
            try:
                _log.debug("generating pending change events")
                for option_name, (old_value, new_value) in self._pending_change_events.items():
                    self._generate_change_event(option_name, old_value, new_value)
            finally:
                self._pending_change_events = None

    def set(
        self,
        option_name: str,
        value: object,
        *,
        from_config: bool = False,
        call_converter: bool | None = None,
        tag: str | None = None,
    ) -> None:
        """Set the value of an opiton.

        Set ``from_config=True`` if the value comes from a configuration
        file (see :meth:`add_option`). That does two things:

            * The converter given to :meth:`add_option` will be used.
            * If the option hasn't been added with :meth:`add_option` yet, then
              the value won't be set immediately, but instead it gets set
              later when the option is added.

        You can specify ``call_converter`` to force the converter to be or
        to not be called.

        Each option has a tag that shows up in :meth:`debug_dump` and :meth:`get_options_by_tag`.
        If the ``tag`` argument is given, the tag of the option will be changed to it.
        Otherwise the tag is cleared.
        Tagging is useful for figuring out where/why an option was set:
        if you call ``.set()`` in two places with different tags,
        the option's current tag tells which of the two places has set the current value.
        """
        if call_converter is None:
            call_converter = from_config

        if option_name not in self._options and from_config:
            self._unknown_options[option_name] = _UnknownOption(value, call_converter, tag)
            return

        option = self._options[option_name]
        if call_converter:
            value = option.converter(value)
        value = _type_check(option.type, value)

        option.tag = tag
        old_value = option.value
        option.value = value
        if old_value != value:
            _log.info(f"changed value of {option_name!r}: {old_value!r} --> {value!r}")

        if self._pending_change_events is None:
            self._generate_change_event(option_name, old_value, value)
        elif option_name in self._pending_change_events:
            # If changed a-->b and then b-->c, add pending change event for (a, c)
            previous_old_value, previous_new_value = self._pending_change_events[option_name]
            assert previous_new_value == old_value
            self._pending_change_events[option_name] = (previous_old_value, value)
        else:
            self._pending_change_events[option_name] = (old_value, value)

    def get_options_by_tag(self, tag: str) -> builtins.set[str]:
        """Return the names of all options whose current value was set with the given ``tag``."""
        return {name for name, option in self._options.items() if option.tag == tag}

    # I don't like how this requires overloads for every type.
    # Also no docstring, because using it from docs/settings.rst showed
    # the messy overloads in the docs.
    # https://stackoverflow.com/q/61471700

    # fmt: off
    @overload
    def get(self, option_name: str, type_: type[Path]) -> Path: ...
    @overload
    def get(self, option_name: str, type_: type[LineEnding]) -> LineEnding: ...
    @overload
    def get(self, option_name: str, type_: type[str]) -> str: ...
    @overload
    def get(self, option_name: str, type_: type[bool]) -> bool: ...
    @overload
    def get(self, option_name: str, type_: type[int]) -> int: ...
    @overload
    def get(self, option_name: str, type_: object) -> Any: ...
    # fmt: on
    def get(self, option_name: str, type_: Any) -> Any:
        result = self._options[option_name].value
        result = _type_check(type_, result)
        return copy.deepcopy(result)  # mutating wouldn't trigger change events

    def debug_dump(self) -> None:
        """Print all settings and their values. This is useful for debugging."""
        print(f"{len(self._options)} known options (add_option called)")
        for name, option in self._options.items():
            print(f"  {name} = {option.value!r}    (type={option.type!r}, tag={option.tag!r})")
        print()

        print(f"{len(self._unknown_options)} unknown options (add_option not called)")
        for name, unknown in self._unknown_options.items():
            string = f"  {name} = {unknown.value!r}    (tag={unknown.tag!r}"
            if not unknown.call_converter:
                string += ", converter function will not be called"
            string += ")"
            print(string)
        print()

    # TODO: document state methods?
    def get_state(self) -> dict[str, _UnknownOption]:
        result = self._unknown_options.copy()
        for name, option in self._options.items():
            value = self.get(name, object)
            if value != option.default:
                result[name] = _UnknownOption(value, call_converter=False, tag=option.tag)
        return result

    def set_state(self, state: dict[str, _UnknownOption]) -> None:
        for name, unknown in state.items():
            self.set(
                name,
                unknown.value,
                from_config=True,
                call_converter=unknown.call_converter,
                tag=unknown.tag,
            )

    def reset(self, option_name: str) -> None:
        """Set an option to its default value given to :meth:`add_option`."""
        self.set(option_name, self._options[option_name].default)

    def reset_all(self) -> None:
        """
        Reset all settings, including the ones not shown in the setting dialog.
        Clicking the reset button of the setting dialog runs this method
        on :data:`global_settings`.
        """
        self._unknown_options.clear()
        for name in self._options:
            self.reset(name)


global_settings = Settings(None, "<<GlobalSettingChanged:{}>>")


# Enum options are stored as name strings, e.g. 'CRLF' for LineEnding.CRLF
# TODO: this is a hack
def _value_to_save(obj: object) -> object:
    if isinstance(obj, enum.Enum):
        return obj.name
    return obj


# Must be a function, so that it updates when tests change the dirs object
def get_json_path() -> Path:
    return dirs.user_config_path / "settings.json"


def save() -> None:
    """Save :data:`global_settings` to the config file.

    Porcupine always calls this when it's closed,
    so usually you don't need to worry about calling this yourself.
    """
    with get_json_path().open("w", encoding="utf-8") as file:
        json.dump(
            {
                name: _value_to_save(unknown_obj.value)
                for name, unknown_obj in global_settings.get_state().items()
            },
            file,
            indent=4,
        )
        file.write("\n")


def _load_from_file() -> None:
    try:
        with get_json_path().open("r", encoding="utf-8") as file:
            options = json.load(file)
    except FileNotFoundError:
        return

    for name, value in options.items():
        global_settings.set(name, value, from_config=True)


# pygments styles can be uninstalled, must not end up with invalid pygments style that way
def _check_pygments_style(name: str) -> str:
    styles.get_style_by_name(name)  # may raise error that will get logged
    return name


# plugin disable list is needed on porcupine startup before anything is done with tkinter
#
# undocumented on purpose, don't use in plugins
def init_enough_for_using_disabled_plugins_list() -> None:
    try:
        _load_from_file()
    except Exception:
        _log.exception(f"reading {get_json_path()} failed")
    global_settings.add_option("disabled_plugins", [], List[str])


def _init_global_gui_settings() -> None:
    global_settings.add_option("pygments_style", "stata-dark", converter=_check_pygments_style)
    global_settings.add_option(
        "default_line_ending", LineEnding(os.linesep), converter=LineEnding.__getitem__
    )

    fixedfont = tkinter.font.Font(name="TkFixedFont", exists=True)
    if fixedfont["size"] < 0:
        # negative sizes have a special meaning in Tk, and i don't care much
        # about it for porcupine, using stupid hard-coded default instead
        fixedfont.config(size=10)

    if sys.platform == "win32":
        # Windows default monospace font sucks, see #245
        default_font_family = "Consolas"
    else:
        # fixedfont['family'] is typically e.g. 'Monospace', that's not included in
        # tkinter.font.families() because it refers to another font family that is
        # in tkinter.font.families()
        default_font_family = fixedfont.actual("family")

    global_settings.add_option("font_family", default_font_family)
    global_settings.add_option("font_size", fixedfont["size"])

    # keep TkFixedFont up to date with settings
    def update_fixedfont(event: tkinter.Event[tkinter.Misc] | None) -> None:
        # can't bind to get_tab_manager() as recommended in docs because tab
        # manager isn't ready yet when settings get inited
        if event is None or event.widget == porcupine.get_main_window():
            fixedfont.config(
                family=global_settings.get("font_family", str),
                size=global_settings.get("font_size", int),
            )

    porcupine.get_main_window().bind(
        "<<GlobalSettingChanged:font_family>>", update_fixedfont, add=True
    )
    porcupine.get_main_window().bind(
        "<<GlobalSettingChanged:font_size>>", update_fixedfont, add=True
    )
    update_fixedfont(None)


def _create_dialog_content() -> ttk.Frame:
    dialog = tkinter.Toplevel()
    dialog.withdraw()
    dialog.title("Porcupine Settings")
    dialog.protocol("WM_DELETE_WINDOW", dialog.withdraw)
    dialog.bind("<Escape>", (lambda event: dialog.withdraw()), add=True)

    def confirm_and_reset_all() -> None:
        if messagebox.askyesno(
            "Reset Settings", "Are you sure you want to reset all settings?", parent=dialog
        ):
            global_settings.reset_all()

    big_frame = ttk.Frame(dialog)
    big_frame.pack(fill="both", expand=True)
    content = ttk.Frame(big_frame)
    content.pack(fill="both", expand=True, padx=5, pady=5)
    ttk.Separator(big_frame).pack(fill="x")
    buttonframe = ttk.Frame(big_frame, padding=5)
    buttonframe.pack(fill="x")

    ttk.Button(
        buttonframe, text="Reset all settings", command=confirm_and_reset_all, width=15
    ).pack(side="left")
    ttk.Button(buttonframe, text="OK", command=dialog.withdraw, width=10).pack(side="right")

    content.grid_columnconfigure(0, weight=1)
    content.grid_columnconfigure(1, weight=1)
    return content


_dialog_content: ttk.Frame | None = None


def show_dialog() -> None:
    """Show the "Porcupine Settings" dialog.

    This function is called when the user opens the dialog from the menu.
    """
    dialog = get_dialog_content().winfo_toplevel()

    if dialog.winfo_viewable():
        dialog.focus()
        return

    dialog.transient(porcupine.get_main_window())
    dialog.deiconify()


def get_dialog_content() -> ttk.Frame:
    """Return the widget where setting changing widgets should be added.

    Use ``settings.get_dialog_content().winfo_toplevel()`` to access the dialog
    itself. It's a :class:`tkinter.Toplevel`.

    Use grid with the returned widget. Its columns are configured like this::

        ,-----------------------------------------------------------.
        | Porcupine Settings                      |  _  |  O  |  X  |
        |-----------------------------------------------------------|
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
        |===========================================================|
        |  ,---------.                                 ,---------.  |
        |  |  Reset  |                                 |   OK    |  |
        |  `---------'                                 `---------'  |
        `-----------------------------------------------------------'

    Column 0 typically contains labels such as "Font Family:", and column 1
    contains widgets for changing the settings. Column 2 is used for displaying
    |triangle| when the user has chosen the setting badly.
    """
    if _dialog_content is None:
        raise RuntimeError("porcupine isn't running")
    return _dialog_content


def _get_blank_triangle_sized_image(*, _cache: list[tkinter.PhotoImage] = []) -> tkinter.PhotoImage:
    # see images/__init__.py
    if not _cache:
        _cache.append(
            tkinter.PhotoImage(
                width=images.get("triangle").width(), height=images.get("triangle").height()
            )
        )
        atexit.register(_cache.clear)
    return _cache[0]


_StrOrInt = TypeVar("_StrOrInt", str, int)


def _create_validation_triangle(
    widget: ttk.Entry,
    option_name: str,
    type_: type[_StrOrInt],
    callback: Callable[[_StrOrInt], bool],
) -> ttk.Label:
    triangle = ttk.Label(widget.master)
    var = tkinter.StringVar()

    def var_changed(*junk: object) -> None:
        value_string = var.get()

        value: _StrOrInt | None
        try:
            value = type_(value_string)
        except ValueError:  # e.g. int('foo')
            value = None
        else:
            if not callback(value):
                value = None

        if value is None:
            triangle.config(image=images.get("triangle"))
        else:
            triangle.config(image=_get_blank_triangle_sized_image())
            global_settings.set(option_name, value, from_config=True)

    def setting_changed(junk: object = None) -> None:
        var.set(str(_value_to_save(global_settings.get(option_name, object))))

    widget.bind(f"<<GlobalSettingChanged:{option_name}>>", setting_changed, add=True)
    var.trace_add("write", var_changed)
    setting_changed()

    widget.config(textvariable=var)
    return triangle


def _grid_widgets(
    label_text: str, chooser: tkinter.Widget, triangle: tkinter.Widget | None
) -> None:
    label = ttk.Label(chooser.master, text=label_text)
    label.grid(column=0, sticky="w")
    chooser.grid(row=label.grid_info()["row"], column=1, sticky="we", pady=5)
    if triangle is not None:
        triangle.grid(row=label.grid_info()["row"], column=2)


def add_entry(
    option_name: str, text: str, validate_callback: Callable[[str], bool], **entry_kwargs: Any
) -> ttk.Entry:
    """Add a :class:`tkinter.ttk.Entry` to the setting dialog.

    A label that displays *text* will be added next to the entry.
    All ``**entry_kwargs`` go to :class:`tkinter.ttk.Entry`.

    When the user types something into the entry, *validate_callback*
    is called with the text of the entry as its only argument.
    If it returns ``True``, then the option given by *option_name*
    is set to the string that the user typed.
    Otherwise |triangle| is shown.
    """
    entry = ttk.Entry(get_dialog_content(), **entry_kwargs)
    triangle = _create_validation_triangle(entry, option_name, str, validate_callback)
    _grid_widgets(text, entry, triangle)
    return entry


def add_checkbutton(option_name: str, **checkbutton_kwargs: Any) -> ttk.Checkbutton:
    """Add a :class:`tkinter.ttk.Checkbutton` to the setting dialog.

    All ``**checkbutton_kwargs`` go to :class:`tkinter.ttk.Checkbutton`.
    You can do this, for example::

        from porcupine import settings
        from porcupine.settings import global_settings

        def do_something() -> None:
            # 'bool' here is a keyword and should not be replaced with 'True' or 'False'
            if settings.get("foobar", bool):
                print("Foobar enabled")
            else:
                print("Foobar disabled")

        def setup() -> None:
            global_settings.add_option("foobar", False)  # False is default value
            settings.add_checkbutton("foobar", text="Enable foobar")

    Currently it is not possible to display a |triangle| next to the
    checkbutton. Let me know if you need it.
    """
    checkbutton = ttk.Checkbutton(get_dialog_content(), **checkbutton_kwargs)
    checkbutton.grid(column=0, columnspan=2, sticky="w", pady=2)

    var = tkinter.BooleanVar()

    def var_changed(*junk: object) -> None:
        value = var.get()
        global_settings.set(option_name, value)

    def setting_changed(junk: object = None) -> None:
        var.set(global_settings.get(option_name, bool))

    checkbutton.bind(f"<<GlobalSettingChanged:{option_name}>>", setting_changed, add=True)
    var.trace_add("write", var_changed)
    setting_changed()

    checkbutton.config(variable=var)
    return checkbutton


def add_combobox(option_name: str, text: str, **combobox_kwargs: Any) -> ttk.Combobox:
    """Add a :class:`tkinter.ttk.Combobox` to the setting dialog.

    All ``**combobox_kwargs`` go to :class:`tkinter.ttk.Combobox`.
    Usually you should pass at least ``values=list_of_strings``.

    The content of the combobox is checked whenever it changes.
    If it's in ``combobox['values']``
    (given with the ``values=list_of_strings`` keyword argument or changed
    later by configuring the returned combobox), then the option given by
    *option_name* is set to the content of the combobox. The converter passed
    to the :meth:`~Settings.add_option` of ``global_settings`` will be used.
    If the content of the combobox is not in ``combobox['values']``,
    then |triangle| is shown.
    """
    combo = ttk.Combobox(get_dialog_content(), **combobox_kwargs)
    triangle = _create_validation_triangle(
        combo, option_name, str, (lambda value: value in combo["values"])
    )
    _grid_widgets(text, combo, triangle)
    return combo


def add_spinbox(option_name: str, text: str, **spinbox_kwargs: Any) -> tkinter.ttk.Spinbox:
    """Add a :class:`tkinter.ttk.Spinbox` to the setting dialog.

    All ``**spinbox_kwargs`` go to :class:`tkinter.ttk.Spinbox`.
    Usually you should pass at least ``from_=some_integer, to=another_integer``.

    The content of the spinbox is checked whenever it changes.
    If it's a valid integer between ``spinbox['from']`` and ``spinbox['to']`` (inclusive),
    then the option given by *option_name* is set to the :class:`int`.
    Otherwise |triangle| is shown.
    """
    spinbox = ttk.Spinbox(get_dialog_content(), **spinbox_kwargs)
    triangle = _create_validation_triangle(
        spinbox, option_name, int, lambda value: int(spinbox["from"]) <= value <= int(spinbox["to"])
    )
    _grid_widgets(text, spinbox, triangle)
    return spinbox


def _get_colors(style_name: str) -> tuple[str, str]:
    style = styles.get_style_by_name(style_name)
    bg = style.background_color

    fg = style.style_for_token(token.String)["color"] or style.style_for_token(token.Text)["color"]
    if fg:
        fg = "#" + fg
    else:
        # yes, style.default_style can be '#rrggbb', '' or nonexistent
        # this is undocumented
        #
        #   >>> from pygments.styles import *
        #   >>> [getattr(get_style_by_name(name), 'default_style', '???')
        #   ...  for name in get_all_styles()]
        #   ['', '', '', '', '', '', '???', '???', '', '', '', '',
        #    '???', '???', '', '#cccccc', '', '', '???', '', '', '', '',
        #    '#222222', '', '', '', '???', '']
        fg = getattr(style, "default_style", "") or utils.invert_color(bg)

    return (fg, bg)


# TODO: document this?
def add_pygments_style_button(option_name: str, text: str) -> None:
    var = tkinter.StringVar()

    # not using ttk.Menubutton because i want custom colors
    menubutton = tkinter.Menubutton(
        get_dialog_content(), textvariable=var, takefocus=True, highlightthickness=1
    )
    menu = tkinter.Menu(menubutton, tearoff=False)
    menubutton.config(menu=menu)

    def var_to_settings(*junk: object) -> None:
        global_settings.set(option_name, var.get())

    def settings_to_var_and_colors(junk: object = None) -> None:
        style_name = global_settings.get(option_name, object)
        var.set(style_name)
        fg, bg = _get_colors(style_name)
        menubutton.config(foreground=fg, background=bg, highlightcolor=fg, highlightbackground=bg)

    menubutton.bind(f"<<GlobalSettingChanged:{option_name}>>", settings_to_var_and_colors, add=True)
    var.trace_add("write", var_to_settings)

    # Not done when creating button, because can slow down porcupine startup
    def fill_menubutton(junk_event: object) -> None:
        menu.delete(0, "end")
        for index, style_name in enumerate(sorted(styles.get_all_styles())):
            fg, bg = _get_colors(style_name)
            menu.add_radiobutton(
                label=style_name,
                value=style_name,
                variable=var,
                foreground=fg,
                background=bg,
                # swapped colors
                activeforeground=bg,
                activebackground=fg,
                columnbreak=(index != 0 and index % 20 == 0),
            )
        settings_to_var_and_colors()

    menubutton.bind("<Map>", fill_menubutton, add=True)
    _grid_widgets(text, menubutton, None)


def add_label(text: str) -> ttk.Label:
    """Add text to the setting dialog.

    This is useful for explaining what some options do with more than a few words.
    The text is always as wide as the dialog is, even when the dialog is resized.
    """
    label = ttk.Label(get_dialog_content(), text=text)
    label.grid(column=0, columnspan=3, sticky="we", pady=10)

    get_dialog_content().bind(
        "<Configure>", (lambda event: label.config(wraplength=event.width)), add=True
    )
    return label


# TODO: document this
def remember_pane_size(
    panedwindow: utils.PanedWindow, pane: tkinter.Misc, option_name: str, default_size: int
) -> None:
    # exist_ok=True to allow e.g. calling this once for each tab
    global_settings.add_option(option_name, default_size, int, exist_ok=True)

    def settings_to_gui(junk: object = None) -> None:
        if panedwindow["orient"] == "horizontal":
            panedwindow.paneconfig(pane, width=global_settings.get(option_name, int))
        else:
            panedwindow.paneconfig(pane, height=global_settings.get(option_name, int))

    def gui_to_settings() -> None:
        if panedwindow["orient"] == "horizontal":
            global_settings.set(option_name, pane.winfo_width())
        else:
            global_settings.set(option_name, pane.winfo_height())

    settings_to_gui()
    pane.bind("<Map>", settings_to_gui, add=True)

    # after_idle helps with accuracy if you move mouse really fast
    panedwindow.bind(
        "<ButtonRelease-1>", (lambda e: panedwindow.after_idle(gui_to_settings)), add=True
    )


def use_pygments_fg_and_bg(
    widget: tkinter.Misc,
    callback: Callable[[str, str], object],
    *,
    option_name: str = "pygments_style",
) -> None:
    """Run a callback whenever the pygments theme changes.

    The callback no longer runs once ``widget`` has been destroyed. It is
    called with the foreground and background color of the pygments theme as
    arguments.
    """

    def on_style_changed(junk: object = None) -> None:
        style = styles.get_style_by_name(global_settings.get(option_name, str))
        # Similar to _get_colors() but doesn't use the color of strings
        bg = style.background_color
        fg = getattr(style, "default_style", "") or utils.invert_color(bg)
        callback(fg, bg)

    widget.bind(f"<<GlobalSettingChanged:{option_name}>>", on_style_changed, add=True)
    on_style_changed()


def _is_monospace(font_family: str) -> bool:
    # Ignore weird fonts starting with @ (happens on Windows)
    if font_family.startswith("@"):
        return False

    # I don't want to create font objects just for this, lol
    tcl_interpreter = get_dialog_content().tk

    # https://core.tcl-lang.org/tk/info/3767882e06
    if "emoji" in font_family.lower():
        return False

    # We can't use "font metrics ... -fixed" because it is sometimes wrong.
    # https://github.com/Akuli/porcupine/issues/1368

    # In non-monospace fonts, i is very narrow and m is very wide.
    # Also, make sure that bolding or italic doesn't change the width.
    sizes = [
        tcl_interpreter.call("font", "measure", (font_family, "12"), "iii"),
        tcl_interpreter.call("font", "measure", (font_family, "12"), "mmm"),
        tcl_interpreter.call("font", "measure", (font_family, "12", "bold"), "mmm"),
        tcl_interpreter.call("font", "measure", (font_family, "12", "italic"), "mmm"),
    ]

    # Allow off-by-one errors, just in case. Don't know if they ever actually happen.
    return max(sizes) - min(sizes) <= 1


def _get_monospace_font_families() -> list[str]:
    cache_path = dirs.user_cache_path / "font_cache.json"
    all_families = sorted(set(tkinter.font.families()))

    # This is surprisingly slow when there are lots of fonts. Let's cache.
    try:
        with cache_path.open("r") as file:
            cache = json.load(file)

        # all_families stored to cache in case user installs more fonts
        if cache["version"] == 3 and cache["all_families"] == all_families:
            _log.debug(f"Taking list of monospace families from {cache_path}")
            return cache["monospace_families"]

    except FileNotFoundError:
        pass
    except Exception:
        _log.error(f"unexpected {cache_path} reading error", exc_info=True)

    _log.warning(f"Can't use {cache_path}. Starting Porcupine might take a while.")
    monospace_families = list(filter(_is_monospace, all_families))

    try:
        with cache_path.open("w") as file:
            json.dump(
                {
                    "version": 3,
                    "all_families": all_families,
                    "monospace_families": monospace_families,
                },
                file,
            )
        _log.debug(f"Wrote {cache_path}")
    except Exception:
        _log.error(f"unexpected {cache_path} writing error", exc_info=True)

    return monospace_families


def _fill_dialog_content_with_defaults() -> None:
    start_time = time.perf_counter()
    monospace_families = _get_monospace_font_families()
    _log.debug(f"Found monospace fonts in {round((time.perf_counter() - start_time)*1000)}ms")

    add_combobox("font_family", "Font family:", values=monospace_families)
    add_spinbox("font_size", "Font size:", from_=3, to=1000)
    add_combobox(
        "default_line_ending", "Default line ending:", values=[ending.name for ending in LineEnding]
    )
    add_pygments_style_button("pygments_style", "Pygments style for editing:")


# undocumented on purpose, don't use in plugins
def init_the_rest_after_initing_enough_for_using_disabled_plugins_list() -> None:
    global _dialog_content
    assert _dialog_content is None

    _log.debug("initializing continues")
    _init_global_gui_settings()
    _dialog_content = _create_dialog_content()
    _fill_dialog_content_with_defaults()
    _log.debug("initialized")
