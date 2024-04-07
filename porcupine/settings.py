from __future__ import annotations

import atexit
import importlib
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
from collections.abc import Generator, Iterator
from pathlib import Path
from tkinter import messagebox, ttk
import typing
from typing import Any, Callable, TypeVar, overload, TYPE_CHECKING, Type, Optional, Literal, cast

import pygments
from pygments import styles, token
from pygments.lexer import LexerMeta

import porcupine
from porcupine import dirs, images, utils

if TYPE_CHECKING:
    from porcupine import tabs

_log = logging.getLogger(__name__)


class LineEnding(enum.Enum):
    r"""This represents different ways to write newline characters to files.

    Python's `open` function translates all of these to `\n` when reading files,
    and uses a platform-specific default when writing files.

    There are 3 ways to represent line endings in Porcupine, and
    different things want the line ending represented in different ways:

    - The strings `"\r"`, `"\n"` and `"\r\n"` (for example, the `open` function wants one of these)
    - The strings `"CR"`, `"LF"` and `"CRLF"` (e.g. [editorconfig](https://editorconfig.org/))
    - This enum

    Converting between this enum and other forms:

        >>> LineEnding["CRLF"]
        <LineEnding.CRLF: '\r\n'>
        >>> LineEnding["CRLF"].value
        '\r\n'
        >>> LineEnding("\r\n")
        <LineEnding.CRLF: '\r\n'>
        >>> LineEnding("\r\n").value
        '\r\n'
    """
    CR = "\r"
    LF = "\n"
    CRLF = "\r\n"


# Let's avoid this legacy quirk:
#    >>> isinstance(True, int)
#    True
def _is_integer(x: object) -> bool:
    return isinstance(x, int) and x is not True and x is not False


# Ints can be treated as floats basically everywhere.
# Python's typing system also accepts ints for "float" parameters.
def _is_float(x: object) -> bool:
    return _is_integer(x) or isinstance(x, float)


def _unwrap_optional(optional: object) -> object:
    """Convert Optional[str] to str."""
    assert str(optional).startswith("typing.Optional[")

    # Optional[str] looks like Union[str, None]
    args = list(typing.get_args(optional))
    assert len(args) == 2
    args.remove(type(None))
    return args[0]


# Please ensure that all functions with this exact comment support the same types.
def _type_check(value: object, expected_type: Any) -> bool:
    if expected_type in (str, bool) or isinstance(expected_type, enum.EnumMeta):
        return isinstance(value, expected_type)

    if expected_type == int:
        return _is_integer(value)

    if expected_type == float:
        return _is_float(value)

    if str(expected_type).startswith("typing.Optional["):
        return value is None or _type_check(value, _unwrap_optional(expected_type))

    if str(expected_type).startswith("list["):
        [list_of_what] = typing.get_args(expected_type)
        return isinstance(value, list) and all(_type_check(item, list_of_what) for item in value)

    if str(expected_type).startswith("dict["):
        key_type, value_type = typing.get_args(expected_type)
        return (
            isinstance(value, dict)
            and all(_type_check(k, key_type) for k in value.keys())
            and all(_type_check(v, value_type) for v in value.values())
        )

    raise NotImplementedError(str(expected_type))


# Please ensure that all functions with this exact comment support the same types.
def _convert_value_from_json_safe(json_safe_value: object, target_type: Any) -> object:
    if target_type == str:
        if not isinstance(json_safe_value, str):
            raise TypeError(f"expected string, got {json_safe_value!r}")
        return json_safe_value

    if target_type == int:
        if not _is_integer(json_safe_value):
            raise TypeError(f"expected integer, got {json_safe_value!r}")
        return json_safe_value

    if target_type == float:
        if not _is_float(json_safe_value):
            raise TypeError(f"expected float, got {json_safe_value!r}")
        return json_safe_value

    if target_type == bool:
        if not isinstance(json_safe_value, bool):
            raise TypeError(f"expected True or False, got {json_safe_value!r}")
        return json_safe_value

    if str(target_type).startswith("typing.Optional["):
        if json_safe_value is None:
            return None
        return _convert_value_from_json_safe(json_safe_value, _unwrap_optional(target_type))

    if str(target_type).startswith("list["):
        if not isinstance(json_safe_value, list):
            raise TypeError(f"expected list, got {json_safe_value!r}")

        [item_type] = typing.get_args(target_type)
        return [
            _convert_value_from_json_safe(item, item_type)
            for item in json_safe_value
        ]

    if str(target_type).startswith("dict["):
        if not isinstance(json_safe_value, dict):
            raise TypeError(f"expected dict, got {json_safe_value!r}")

        key_type, value_type = typing.get_args(target_type)
        return {
            _convert_value_from_json_safe(k, key_type): _convert_value_from_json_safe(v, value_type)
            for k, v in json_safe_value.items()
        }

    if isinstance(target_type, enum.EnumMeta):
        if not isinstance(json_safe_value, str):
            # TODO: add test?
            raise TypeError(f"expected string (must belong to the {target_type.__name__} enum), got {json_safe_value!r}")
        return target_type[json_safe_value]

    raise NotImplementedError(str(target_type))


# Please ensure that all functions with this exact comment support the same types.
def _convert_value_to_json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return [_convert_value_to_json_safe(item) for item in value]

    if isinstance(value, dict):
        assert all(isinstance(k, str) for k in value.keys()), "JSON only supports string keys"
        return {k: _convert_value_to_json_safe(v) for k, v in value.items()}

    if isinstance(value, enum.Enum):
        return value.name

    raise NotImplementedError(str(value))


@dataclasses.dataclass
class _KnownOption:
    type: Any
    value: object
    default_value: object


# includes the parent
def _get_children_recursively(parent: tkinter.Misc) -> Iterator[tkinter.Misc]:
    yield parent
    for child in parent.winfo_children():
        yield from _get_children_recursively(child)


_T = TypeVar("_T")


class Settings:
    def __init__(self, tab: tabs.Tab | None) -> None:
        self._tab = tab  # None if global settings
        self._unknown_options: dict[str, object] = {}
        self._known_options: dict[str, _KnownOption] = {}
        self._pending_change_events: dict[str, tuple[object, object]] | None = None

    def add_option(
        self, option_name: str, *, type: Any, default: object, exist_ok: bool = False
    ) -> None:
        """Add an option to settings.

        Example:

            global_settings.add_option("foo", type=bool, default=True)

        If the option accepts `None`, you need to use `typing.Optional`, because
        Porcupine still supports Python 3.9:

            global_settings.add_option("extra_thingy", type=Optional[str], default=None)

        If an option with the same name exists already, an error is raised by
        default, but if `exist_ok=True` is given, then adding the same option
        multiple times is fine, as long as `type` and `default` are the same
        every time.
        """
        if option_name in self._known_options:
            if not exist_ok:
                raise RuntimeError(f"there's already an option named {option_name!r}")
            old_option = self._known_options[option_name]
            assert type == old_option.type
            assert default == old_option.default_value
            return

        if not _type_check(default, type):
            raise TypeError(f"default value {default!r} doesn't match the specified type {type!r}")

        self._known_options[option_name] = _KnownOption(
            type=type, value=default, default_value=default
        )

        try:
            raw_value = self._unknown_options.pop(option_name)
        except KeyError:
            pass  # nothing relevant in config file, use default
        else:
            # Error handling here because bad data in a config file shouldn't
            # cause add_option() and the rest of a plugin's setup() to fail.
            try:
                value = _convert_value_from_json_safe(raw_value, type)
            except Exception:
                _log.exception(
                    f"setting {option_name!r} to {raw_value!r} failed, falling back to default: {default!r}"
                )
            else:
                self.set(option_name, value)

    def _generate_change_event(
        self, option_name: str, old_value: object, new_value: object
    ) -> None:
        if self._tab is None:
            event_name = f"<<GlobalSettingChanged:{option_name}>>"
        else:
            event_name = f"<<TabSettingChanged:{option_name}>>"

        if old_value == new_value:
            _log.debug(f"not generating a change event because value didn't change: {event_name}")
            return

        _log.info(f"generating change event: {event_name}")

        if self._tab is None:
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
            self._tab.event_generate(event_name)

    # TODO: document this
    @contextlib.contextmanager
    def defer_change_events(self) -> Generator[None, None, None]:
        """A context manager that runs all change events for several changes at once.

        Usage:

            with global_settings.defer_change_events():
                global_settings.set("font_family", "Noto Sans Mono")
                global_settings.set("font_size", 12)
                global_settings.set("font_size", 14)
                global_settings.set("font_size", 15)
                # No change events ran yet.

            # When we get here ("with" statement ends), we get only two change events:
            #   <<GlobalSettingChanged:font_family>>
            #   <<GlobalSettingChanged:font_size>>    (this only runs once!)
        """
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

    def set(self, option_name: str, value: object) -> None:
        """Set the value of an opiton."""
        if option_name not in self._known_options:
            # TODO: add test for this
            raise ValueError(
                f"option {option_name!r} doesn't exist, because `add_option({option_name!r}, ...)` was not called"
            )

        option = self._known_options[option_name]
        if not _type_check(value, option.type):
            raise TypeError(
                f"value of {option_name!r} must be of type {option.type}, not {value!r}"
            )

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

    def set_json_safe_value(self, option_name: str, json_safe_value: object) -> None:
        """Set the value of an option using a raw JSON-safe value.

        For example, for `pathlib.Path` options, this method wants a string
        whereas `.set()` wants a `pathlib.Path` object.

        Also, with this method, the option doesn't need to be known yet.
        """
        if option_name in self._known_options:
            target_type = self._known_options[option_name].type
            self.set(option_name, _convert_value_from_json_safe(json_safe_value, target_type))
        else:
            self._unknown_options[option_name] = json_safe_value

    # fmt: off
    @overload
    def get(self, option_name: str, type: type[_T], *, can_be_none: Literal[True]) -> _T | None: ...
    @overload
    def get(self, option_name: str, type: type[_T]) -> _T: ...
    # fmt: on

    def get(self, option_name: str, type: type[_T], can_be_none: bool = False) -> _T:
        """Returns the current value of an option.

        The `type` must be the same type that what was passed into `add_option()`.

        If you want to get the value of an option that can be `None`, pass the
        type without `None` and set `can_be_none=True`. So instead of one of these:

            value = global_settings.get("foo", str | None)      # bad
            value = global_settings.get("foo", Optional[str])   # bad

        You need to do this:

            value = global_settings.get("foo", str, can_be_none=True)  # good

        This works around a mypy bug/limitation. See https://stackoverflow.com/q/61471700
        """
        if option_name not in self._known_options:
            # TODO: add test for this
            raise ValueError(
                f"option {option_name!r} doesn't exist, because `add_option({option_name!r}, ...)` was not called"
            )

        if can_be_none:
            type = Optional[type]  # type: ignore

        expected_type = self._known_options[option_name].type
        if type != expected_type:
            # TODO: add test for this
            raise TypeError(
                f"wrong type {type!r} specified to .get(), should be {expected_type} because"
                + f" the option was added with `add_option({option_name!r}, type={expected_type}, ...)`"
            )

        # Mutating the result would be wrong because it wouldn't trigger change events.
        # Instead of telling developers to not mutate, let's make a copy so that mutating is pointless.
        result = copy.deepcopy(self._known_options[option_name].value)
        return cast(_T, result)

    def get_json_safe_value(self, option_name: str) -> object:
        """Return the value of an option as it would be saved to a JSON file."""
        if option_name not in self._known_options:
            # TODO: add test for this
            raise ValueError(
                f"option {option_name!r} doesn't exist, because `add_option({option_name!r}, ...)` was not called"
            )

        return _convert_value_to_json_safe(self._known_options[option_name].value)

    # TODO: check that this works, if there isn't a test for it.
    def debug_dump(self) -> None:
        """Print all settings and their values. This is useful for debugging."""
        print(f"{len(self._known_options)} known options (add_option called)")
        for name, option in self._known_options.items():
            print(
                f"  {name} = {option.value!r}    (type={option.type!r}, default={option.default_value!r})"
            )
        print()

        print(f"{len(self._unknown_options)} unknown options (add_option not called)")
        for name, unknown_value in self._unknown_options.items():
            print(f"  {name} = {unknown_value!r}")
        print()

    def get_state(self) -> dict[str, object]:
        """Return the value that is saved to the JSON file."""
        result = self._unknown_options.copy()
        for name, option in self._known_options.items():
            if option.value != option.default_value:
                result[name] = _convert_value_to_json_safe(option.value)
        return result

    def set_state(self, state: dict[str, object]) -> None:
        """Load settings from a value that came from a JSON file."""
        for name, value in state.items():
            self.set_json_safe_value(name, value)

    def reset(self, option_name: str) -> None:
        """Set an option to its default value given to :meth:`add_option`."""
        self.set(option_name, self._known_options[option_name].default_value)

    def reset_all(self) -> None:
        """Reset all settings to their defaults. This includes unknown options!

        Clicking the reset button of the setting dialog runs this method
        on `global_settings`.
        """
        self._unknown_options.clear()
        with self.defer_change_events():
            for name in self._known_options.keys():
                self.reset(name)


global_settings = Settings(tab=None)


# Must be a function, so that it updates when tests change the dirs object
def get_json_path() -> Path:
    return dirs.user_config_path / "settings.json"


# TODO: call save() more frequently
def save() -> None:
    """Save `global_settings` to `settings.json`.

    Porcupine always calls this when it's closed,
    so usually you don't need to worry about calling this yourself.
    """
    # First create string of JSON, so that writing is less likely to leave the file corrupt.
    big_string = json.dumps(global_settings.get_state(), indent=4) + "\n"
    get_json_path().write_text(big_string, encoding="utf-8")


def _load_from_file() -> None:
    try:
        with get_json_path().open("r", encoding="utf-8") as file:
            options = json.load(file)
    except FileNotFoundError:
        return
    global_settings.set_state(options)


# plugin disable list is needed on porcupine startup before anything is done with tkinter
#
# undocumented on purpose, don't use in plugins
def init_enough_for_using_disabled_plugins_list() -> None:
    try:
        _load_from_file()
    except Exception:
        _log.exception(f"reading {get_json_path()} failed")
    global_settings.add_option("disabled_plugins", type=list[str], default=[])


def import_pygments_lexer_class(name: str) -> LexerMeta:
    """Given a string like "pygments.lexers.BashLexer", import the corresponding class.

    This shouldn't be used with untrusted strings, because importing can run
    arbitrary code
    """
    modulename, classname = name.rsplit(".", 1)
    module = importlib.import_module(modulename)
    klass = getattr(module, classname)
    if not isinstance(klass, LexerMeta):
        raise TypeError(f"expected a Lexer subclass, got {klass}")
    return klass


# TODO: add test
def _check_pygments_style() -> None:
    name = global_settings.get("pygments_style", str)
    try:
        styles.get_style_by_name(name)
    except pygments.util.ClassNotFound:
        # This happens if the user removes a pygments style.
        # It is possible to install third-party pygments style packages.
        _log.warning(f"'pygments_style' is set to {name!r} which seems wrong, resetting")
        global_settings.reset("pygments_style")


def _init_global_gui_settings() -> None:
    global_settings.add_option("pygments_style", type=str, default="stata-dark")
    _check_pygments_style()

    global_settings.add_option(
        "default_line_ending", type=LineEnding, default=LineEnding(os.linesep)
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

    global_settings.add_option("font_family", type=str, default=default_font_family)
    global_settings.add_option("font_size", type=int, default=fixedfont["size"])

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
            global_settings.set_json_safe_value(option_name, value)  # this is used with enums

    def setting_changed(junk: object = None) -> None:
        var.set(str(global_settings.get_json_safe_value(option_name)))

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
        style_name = global_settings.get(option_name, str)
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
    global_settings.add_option(option_name, type=int, default=default_size, exist_ok=True)

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
    _log.debug(f"checking whether font {font_family!r} is monospace")

    # Ignore weird fonts starting with @ (happens on Windows)
    if font_family.startswith("@"):
        return False

    # I don't want to create font objects just for this, lol
    tcl_interpreter = get_dialog_content().tk

    # "Noto Color Emoji" font causes segfault: https://core.tcl-lang.org/tk/info/3767882e06
    #
    # There is also segfault with "Amiri Quran Colored" font (see #1442).
    # I haven't reported to Tk's bug tracker because I couldn't reproduce it myself.
    if "emoji" in font_family.lower() or "colored" in font_family.lower():
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
