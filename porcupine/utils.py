"""Handy utility functions."""
from __future__ import annotations

import codecs
import collections
import contextlib
import dataclasses
import functools
import json
import logging
import re
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter
import traceback
from pathlib import Path
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Callable, Type, TypeVar
from urllib.request import url2pathname

import dacite

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

import porcupine

log = logging.getLogger(__name__)
_T = TypeVar("_T")


# nsis install puts Porcupine.exe and python.exe in same place
if sys.platform == "win32" and sys.executable.endswith((r"\Porcupine.exe", r"\pythonw.exe")):
    running_pythonw = True
    python_executable = Path(sys.executable).parent / "python.exe"
else:
    running_pythonw = False
    python_executable = Path(sys.executable)


if sys.platform == "win32":
    # this is mostly copy/pasted from subprocess.list2cmdline
    def quote(string: str) -> str:
        result = []
        needquote = False
        bs_buf = []

        needquote = (" " in string) or ("\t" in string) or not string
        if needquote:
            result.append('"')

        for c in string:
            if c == "\\":
                # Don't know if we need to double yet.
                bs_buf.append(c)
            elif c == '"':
                # Double backslashes.
                result.append("\\" * len(bs_buf) * 2)
                bs_buf = []
                result.append('\\"')
            else:
                # Normal char
                if bs_buf:
                    result.extend(bs_buf)
                    bs_buf = []
                result.append(c)

        # Add remaining backslashes, if any.
        if bs_buf:
            result.extend(bs_buf)

        if needquote:
            result.extend(bs_buf)
            result.append('"')

        return "".join(result)


else:
    quote = shlex.quote


# https://github.com/python/typing/issues/769
def copy_type(f: _T) -> Callable[[Any], _T]:
    """A decorator to tell mypy that one function or method has the same type as another.

    Example::

        from typing import Any
        from porcupine.utils import copy_type

        def foo(x: int) -> None:
            print(x)

        @copy_type(foo)
        def bar(*args: Any, **kwargs: Any) -> Any:
            foo(*args, **kwargs)

        bar(1)      # ok
        bar("lol")  # mypy error
    """
    return lambda x: x


# TODO: document this?
def format_command(command: str, substitutions: dict[str, Any]) -> list[str]:
    parts = shlex.split(command, posix=(sys.platform != "win32"))
    return [part.format_map(substitutions) for part in parts]


# There doesn't seem to be standard library trick that works in all cases
# https://stackoverflow.com/q/5977576
#
# TODO: document this?
def file_url_to_path(file_url: str) -> Path:
    assert file_url.startswith("file://")

    if sys.platform == "win32":
        if file_url.startswith("file:///"):
            # File on this computer: 'file:///C:/Users/Akuli/Foo%20Bar.txt'
            return Path(url2pathname(file_url[8:]))
        else:
            # Network share: 'file://Server2/Share/Test/Foo%20Bar.txt'
            return Path(url2pathname(file_url[5:]))
    else:
        # 'file:///home/akuli/foo%20bar.txt'
        return Path(url2pathname(file_url[7:]))


# Using these with subprocess prevents opening unnecessary cmd windows
# TODO: document this
subprocess_kwargs: dict[str, Any] = {}
if sys.platform == "win32":
    # https://stackoverflow.com/a/1813893
    subprocess_kwargs["startupinfo"] = subprocess.STARTUPINFO(
        dwFlags=subprocess.STARTF_USESHOWWINDOW
    )


_LIKELY_PROJECT_ROOT_THINGS = [".editorconfig"] + [
    readme + extension
    for readme in ["README", "readme", "Readme", "ReadMe"]
    for extension in ["", ".txt", ".md", ".rst"]
]


def find_project_root(project_file_path: Path) -> Path:
    """Given an absolute path to a file, figure out what project it belongs to.

    The concept of a project is explained
    `in Porcupine wiki <https://github.com/Akuli/porcupine/wiki/Working-with-projects>`_.
    Currently, the logic for finding the project root is:

    1.  If the file is inside a Git repository, then the Git repository becomes
        the project root. For example, the file I'm currently editing is
        ``/home/akuli/porcu/porcupine/utils.py``, and Porcupine has detected
        ``/home/akuli/porcu`` as its project because I use Git to develop Porcupine.
    2.  If Git isn't used but there is a readme file or an ``.editorconfig`` file,
        then the project root is the folder containing the readme or the ``.editorconfig`` file.
        (Porcupine supports editorconfig files.
        You can read more about them at `editorconfig.org <https://editorconfig.org/>`_.)
        So, even if Porcupine didn't use Git, it would still recognize the
        project correctly, because there is ``/home/akuli/porcu/README.md``.
        Porcupine recognizes several different capitalizations and file extensions,
        such as ``README.md``, ``ReadMe.txt`` and ``readme.rst`` for example.
    3.  If all else fails, the directory containing the file is used.
    """
    assert project_file_path.is_absolute()

    likely_root = None
    for path in project_file_path.parents:
        if (path / ".git").exists():
            return path  # trust this the most, if it exists
        elif likely_root is None and any(
            (path / thing).exists() for thing in _LIKELY_PROJECT_ROOT_THINGS
        ):
            likely_root = path

    return likely_root or project_file_path.parent


class PanedWindow(tkinter.PanedWindow):
    """Like :class:`tkinter.PanedWindow`, but uses Ttk colors.

    Do not waste your time with ``ttk.Panedwindow``. It lacks options to
    control the sizes of the panes.
    """

    @copy_type(tkinter.PanedWindow.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # even non-ttk widgets can handle <<ThemeChanged>>
        self.bind("<<ThemeChanged>>", self._update_colors, add=True)
        self._update_colors()

    def _update_colors(self, junk_event: object = None) -> None:
        ttk_bg = self.tk.eval("ttk::style lookup TLabel.label -background")
        assert ttk_bg
        self["bg"] = ttk_bg


# TODO: document this?
def is_bright(color: str) -> bool:
    widget = porcupine.get_main_window()  # any widget would do
    return sum(widget.winfo_rgb(color)) / 3 > 0x7FFF


# i know, i shouldn't do math with rgb colors, but this is good enough
def invert_color(color: str, *, black_or_white: bool = False) -> str:
    """Return a color with opposite red, green and blue values.

    Example: ``invert_color('white')`` is ``'#000000'`` (black).

    This function uses tkinter for converting the color to RGB. That's
    why a tkinter root window must have been created, but *color* can be
    any Tk-compatible color string, like a color name or a ``'#rrggbb'``
    string. The return value is always a ``'#rrggbb`` string (also compatible
    with Tk).

    If ``black_or_white=True`` is set, then the result is always ``"#000000"``
    (black) or ``"#ffffff"`` (white), depending on whether the color is bright
    or dark.
    """
    if black_or_white:
        return "#000000" if is_bright(color) else "#ffffff"

    widget = porcupine.get_main_window()  # any widget would do

    # tkinter uses 16-bit colors, convert them to 8-bit
    r, g, b = (value >> 8 for value in widget.winfo_rgb(color))
    return "#%02x%02x%02x" % (0xFF - r, 0xFF - g, 0xFF - b)


def mix_colors(color1: str, color2: str, color1_amount: float) -> str:
    """Create a new color based on two existing colors.

    The ``color1_amount`` should be a number between 0 and 1, specifying how
    much ``color1`` to use. If you set it to 0.8, for example, then the
    resulting color will be 80% ``color1`` and 20% ``color2``.

    Colors are specified and returned similarly to :func:`invert_color`.
    """
    color2_amount = 1 - color1_amount

    widget = porcupine.get_main_window()
    r, g, b = (
        round(color1_amount * value1 + color2_amount * value2)
        for value1, value2 in zip(widget.winfo_rgb(color1), widget.winfo_rgb(color2))
    )
    return "#%02x%02x%02x" % (r >> 8, g >> 8, b >> 8)  # convert back to 8-bit


# This doesn't handle all possible cases, see bind(3tk)
def _format_binding(binding: str, menu: bool) -> str:
    mac = porcupine.get_main_window().tk.eval("tk windowingsystem") == "aqua"
    parts = binding.lstrip("<").rstrip(">").split("-")

    # don't know how to show click in mac menus
    if mac and menu and any(parts[i : i + 2] == "Button-1".split("-") for i in range(len(parts))):
        return ""

    # Must recompute length on every iteration, because length changes
    i = 0
    while i < len(parts):
        if parts[i : i + 3] == ["Double", "Button", "1"]:
            parts[i : i + 3] = ["double-click"]
        elif parts[i : i + 2] == ["Button", "1"]:
            parts[i : i + 2] = ["click"]
        elif re.fullmatch(r"[a-z]", parts[i]):
            parts[i] = parts[i].upper()
        elif re.fullmatch(r"[A-Z]", parts[i]):
            parts.insert(i, "Shift")
            # Increment beyond the added "Shift" and letter
            i += 2
            continue

        i += 1

    if "Key" in parts:
        parts.remove("Key")

    if mac:
        # event_info() returns <Mod1-Key-x> for <Command-x>
        parts = [{"Mod1": "Command", "plus": "+", "minus": "-"}.get(part, part) for part in parts]

    if mac:
        # <ThePhilgrim> I think it's like from left to right... so it would be shift -> ctrl -> alt -> cmd
        sort_order = {"Shift": 1, "Control": 2, "Alt": 3, "Command": 4}
        symbol_mapping = {
            "Shift": "⇧",
            "Control": "⌃",  # NOT same as ascii "^"
            "Alt": "⌥",
            "Command": "⌘",
            "Return": "⏎",
        }
    else:
        sort_order = {"Control": 1, "Alt": 2, "Shift": 3}
        symbol_mapping = {
            "Control": "Ctrl",
            "0": "Zero",  # not needed on mac, its font distinguishes 0 and O well
            "plus": "Plus",
            "minus": "Minus",
            "Return": "Enter",
        }
    parts.sort(key=(lambda part: sort_order.get(part, 100)))

    if mac and menu:
        # Tk will use the proper symbols automagically, and it expects dash-separated
        # Even "Command--" for command and minus key works
        return "-".join(parts)

    parts = [symbol_mapping.get(part, part) for part in parts]

    if mac:
        # e.g. "⌘-double-click"
        # But not like this:  ["double-click"] --> ["-double-click"]
        parts[1:] = [
            {"click": "-click", "double-click": "-double-click"}.get(part, part)
            for part in parts[1:]
        ]

    return ("" if mac else "+").join(parts)


# TODO: document this
def get_binding(virtual_event: str, *, menu: bool = False, many: bool = False) -> str:
    bindings = porcupine.get_main_window().event_info(virtual_event)
    replaced_binds = []
    for binding in bindings:
        replaced_binds.append(binding.replace("ButtonRelease-1", "click"))

    if not replaced_binds and not menu:
        log.warning(f"no bindings configured for {virtual_event}")
    results = [_format_binding(b, menu) for b in replaced_binds]
    if not many:
        del results[1:]
    return " or ".join(results)


# TODO: document this
def tkinter_safe_string(string: str, *, hide_unsupported_chars: bool = False) -> str:
    if hide_unsupported_chars:
        replace_with = ""
    else:
        replace_with = "\N{replacement character}"

    return "".join(replace_with if ord(char) > 0xFFFF else char for char in string)


class EventDataclass:
    """
    Inherit from this class when creating a dataclass for
    :func:`bind_with_data`.

    All values should be JSON safe or data classes containing JSON safe values.
    Nested dataclasses don't need to inherit from EventDataclass. Example::

        import dataclasses
        from typing import List
        from porcupine import utils

        @dataclasses.dataclass
        class Foo:
            message: str
            num: int

        @dataclasses.dataclass
        class Bar(utils.EventDataclass):
            foos: List[Foo]

        def handle_event(event: utils.EventWithData) -> None:
            print(event.data_class(Bar).foos[0].message)

        utils.bind_with_data(some_widget, '<<Thingy>>', handle_event, add=True)
        ...
        foos = [Foo('ab', 123), Foo('cd', 456)]
        some_widget.event_generate('<<Thingy>>', data=Bar(foos))

    Note that before Python 3.10, you need ``List[str]`` instead of
    ``list[str]``, even if you use ``from __future__ import annotations``. This
    is because Porcupine uses a library that needs to evaluate the type
    annotations even if ``from __future__ import annotations``
    was used.
    """

    def __str__(self) -> str:
        # str(Foo(a=1, b=2)) --> 'Foo{"a": 1, "b": 2}'
        # Content after Foo is JSON parsed in Event.data_class()
        return type(self).__name__ + json.dumps(dataclasses.asdict(self))


if TYPE_CHECKING:
    _Event = tkinter.Event[tkinter.Misc]
else:
    _Event = tkinter.Event


class EventWithData(_Event):
    """A subclass of :class:`tkinter.Event[tkinter.Misc]` for use with :func:`bind_with_data`."""

    #: If a string was passed to the ``data`` argument of ``event_generate()``,
    #: then this is that string.
    data_string: str

    def data_class(self, T: Type[_T]) -> _T:
        """
        If a dataclass instance of type ``T`` was passed as ``data`` to
        ``event_generate()``, then this returns a copy of it. Otherwise this
        raises an error.

        ``T`` must be a dataclass that inherits from :class:`EventDataclass`.
        """
        assert self.data_string.startswith(T.__name__ + "{")
        result = dacite.from_dict(T, json.loads(self.data_string[len(T.__name__) :]))
        assert isinstance(result, T)
        return result

    def __repr__(self) -> str:
        match = re.fullmatch(r"<(.*)>", super().__repr__())
        assert match is not None
        return f"<{match.group(1)} data_string={self.data_string!r}>"


def bind_with_data(
    widget: tkinter.Misc,
    sequence: str,
    callback: Callable[[EventWithData], str | None],
    add: bool = False,
) -> str:
    """
    Like ``widget.bind(sequence, callback)``, but supports the ``data``
    argument of ``event_generate()``. Note that the callback takes an argument
    of type :class:`EventWithData` rather than a usual ``tkinter.Event[tkinter.Misc]``.

    Here's an example::

        from porcupine import utils

        def handle_event(event: utils.EventWithData):
            print(event.data_string)

        utils.bind_with_data(some_widget, '<<Thingy>>', handle_event, add=True)

        # this prints 'wut wut'
        some_widget.event_generate('<<Thingy>>', data='wut wut')

    Note that everything is a string in Tcl, so tkinter ``str()``'s the data.
    """
    # tkinter creates event objects normally and appends them to the
    # deque, then run_callback() adds data_blablabla attributes to the
    # event objects and runs callback(event)
    #
    # TODO: is it possible to do this without a deque?
    event_objects: collections.deque[tkinter.Event[tkinter.Misc]] = collections.deque()
    widget.bind(sequence, event_objects.append, add=add)

    def run_the_callback(data_string: str) -> str | None:
        event: tkinter.Event[tkinter.Misc] | EventWithData = event_objects.popleft()
        event.__class__ = EventWithData  # evil haxor muhaha
        assert isinstance(event, EventWithData)
        event.data_string = data_string
        return callback(event)  # may return 'break'

    # tkinter's bind() ignores the add argument when the callback is a string :(
    funcname = widget.register(run_the_callback)
    widget.tk.call("bind", widget, sequence, '+ if {"[%s %%d]" == "break"} break' % funcname)
    return funcname


def add_scroll_command(
    widget: tkinter.Text,
    option: Literal["xscrollcommand", "yscrollcommand"],
    callback: Callable[[], None],
) -> None:
    """Schedule ``callback`` to run with no arguments when ``widget`` is scrolled.

    The option should be ``'xscrollcommand'`` for horizontal scrolling or
    ``'yscrollcommand'`` for vertical scrolling.

    Unlike when setting the option directly, this function can be called
    multiple times with the same widget and the same option to set multiple
    callbacks.
    """
    if not widget[option]:
        widget[option] = lambda *args: None
    tcl_code = widget[option]
    assert isinstance(tcl_code, str)
    assert tcl_code

    # from options(3tk): "... the widget will generate a Tcl command by
    # concatenating the scroll command and two numbers."
    #
    # So if tcl_code is like this:  bla bla bla
    #
    # it would be called like this:  bla bla bla 0.123 0.456
    #
    # and by putting something in front on separate line we can make it get called like this
    #
    #   something
    #   bla bla bla 0.123 0.456
    widget[option] = widget.register(callback) + "\n" + tcl_code


# this is not bind_tab to avoid confusing with tabs.py, as in browser tabs
def bind_tab_key(
    widget: tkinter.Widget, on_tab: Callable[["tkinter.Event[Any]", bool], Any], **bind_kwargs: Any
) -> None:
    """A convenience function for binding Tab and Shift+Tab.

    Use this function like this::

        def on_tab(event, shifted):
            # shifted is True if the user held down shift while pressing
            # tab, and False otherwise
            ...

        utils.bind_tab_key(some_widget, on_tab, add=True)

    The ``event`` argument and ``on_tab()`` return values are treated
    just like with regular bindings.

    Binding ``'<Tab>'`` works just fine everywhere, but binding
    ``'<Shift-Tab>'`` only works on Windows and Mac OSX. This function
    also works on X11.
    """
    # there's something for this in more_functools, but it's a big
    # dependency for something this simple imo
    def callback(shifted: bool, event: tkinter.Event[tkinter.Misc]) -> Any:
        return on_tab(event, shifted)

    if widget.tk.call("tk", "windowingsystem") == "x11":
        # even though the event keysym says Left, holding down the right
        # shift and pressing tab also works :D
        shift_tab = "<ISO_Left_Tab>"
    else:
        shift_tab = "<Shift-Tab>"

    widget.bind("<Tab>", functools.partial(callback, False), **bind_kwargs)  # bindcheck: ignore
    widget.bind(shift_tab, functools.partial(callback, True), **bind_kwargs)  # bindcheck: ignore


# list of encodings supported by python 3.7 https://stackoverflow.com/a/25584253
_list_of_encodings = [
    "ascii",
    "big5",
    "big5hkscs",
    "cp037",
    "cp273",
    "cp424",
    "cp437",
    "cp500",
    "cp720",
    "cp737",
    "cp775",
    "cp850",
    "cp852",
    "cp855",
    "cp856",
    "cp857",
    "cp858",
    "cp860",
    "cp861",
    "cp862",
    "cp863",
    "cp864",
    "cp865",
    "cp866",
    "cp869",
    "cp874",
    "cp875",
    "cp932",
    "cp949",
    "cp950",
    "cp1006",
    "cp1026",
    "cp1125",
    "cp1140",
    "cp1250",
    "cp1251",
    "cp1252",
    "cp1253",
    "cp1254",
    "cp1255",
    "cp1256",
    "cp1257",
    "cp1258",
    "cp65001",
    "euc-jis-2004",
    "euc-jisx0213",
    "euc-jp",
    "euc-kr",
    "gb2312",
    "gb18030",
    "gbk",
    "hz",
    "iso2022-jp",
    "iso2022-jp-1",
    "iso2022-jp-2",
    "iso2022-jp-3",
    "iso2022-jp-2004",
    "iso2022-jp-ext",
    "iso2022-kr",
    "iso8859-2",
    "iso8859-3",
    "iso8859-4",
    "iso8859-5",
    "iso8859-6",
    "iso8859-7",
    "iso8859-8",
    "iso8859-9",
    "iso8859-10",
    "iso8859-11",
    "iso8859-13",
    "iso8859-14",
    "iso8859-15",
    "iso8859-16",
    "johab",
    "koi8-r",
    "koi8-t",
    "koi8-u",
    "kz1048",
    "latin-1",
    "mac-cyrillic",
    "mac-greek",
    "mac-iceland",
    "mac-latin2",
    "mac-roman",
    "mac-turkish",
    "ptcp154",
    "shift-jis",
    "shift-jis-2004",
    "shift-jisx0213",
    "utf-7",
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-be",
    "utf-16-le",
    "utf-32",
    "utf-32-be",
    "utf-32-le",
]


# TODO: document this?
def ask_encoding(text: str, old_encoding: str) -> str | None:
    label_width = 400

    dialog = tkinter.Toplevel()
    if porcupine.get_main_window().winfo_viewable():
        dialog.transient(porcupine.get_main_window())
    dialog.resizable(False, False)
    dialog.title("Choose an encoding")

    big_frame = ttk.Frame(dialog)
    big_frame.pack(fill="both", expand=True)
    ttk.Label(big_frame, text=text, wraplength=label_width).pack(fill="x", padx=10, pady=10)

    var = tkinter.StringVar()
    combobox = ttk.Combobox(big_frame, values=_list_of_encodings, textvariable=var)
    combobox.pack(pady=40)
    combobox.set(old_encoding)

    ttk.Label(
        big_frame,
        text=(
            "You can create a project-specific .editorconfig file to change the encoding"
            " permanently."
        ),
        wraplength=label_width,
    ).pack(fill="x", padx=10, pady=10)
    button_frame = ttk.Frame(big_frame)
    button_frame.pack(fill="x", pady=10)

    selected_encoding = None

    def select_encoding() -> None:
        nonlocal selected_encoding
        selected_encoding = combobox.get()
        dialog.destroy()

    cancel_button = ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=1)
    cancel_button.pack(side="left", expand=True, fill="x", padx=10)
    ok_button = ttk.Button(button_frame, text="OK", command=select_encoding, width=1)
    ok_button.pack(side="right", expand=True, fill="x", padx=10)

    def validate_encoding(*junk: object) -> None:
        encoding = combobox.get()
        try:
            codecs.lookup(encoding)
        except LookupError:
            ok_button.config(state="disabled")
        else:
            ok_button.config(state="normal")

    var.trace_add("write", validate_encoding)
    combobox.bind("<Return>", (lambda event: ok_button.invoke()), add=True)
    combobox.bind("<Escape>", (lambda event: cancel_button.invoke()), add=True)
    combobox.select_range(0, "end")
    combobox.focus()

    dialog.wait_window()
    return selected_encoding


def run_in_thread(
    blocking_function: Callable[[], _T],
    done_callback: Callable[[bool, str | _T], None],
    *,
    check_interval_ms: int = 100,
    daemon: bool = True,
) -> None:
    """Run ``blocking_function()`` in another thread.

    If the *blocking_function* raises an error,
    ``done_callback(False, traceback)`` will be called where *traceback*
    is the error message as a string. If no errors are raised,
    ``done_callback(True, result)`` will be called where *result* is the
    return value from *blocking_function*. The *done_callback* is always
    called from Tk's main loop, so it can do things with Tkinter widgets
    unlike *blocking_function*.

    Internally, this function checks whether the thread has completed every
    100 milliseconds by default (so 10 times per second). Specify
    *check_interval_ms* to customize this.

    Unlike :class:`threading.Thread`, this function uses a daemon thread by
    default. This means that the thread will end forcefully when Porcupine
    exits, and it might not get a chance to finish whatever it is doing. Pass
    ``daemon=False`` to change this.
    """
    root = porcupine.get_main_window()  # any widget would do

    value: _T
    error_traceback: str | None = None

    def thread_target() -> None:
        nonlocal value
        nonlocal error_traceback

        try:
            value = blocking_function()
        except Exception:
            error_traceback = traceback.format_exc()

    def check() -> None:
        if thread.is_alive():
            # let's come back and check again later
            root.after(check_interval_ms, check)
        else:
            if error_traceback is None:
                done_callback(True, value)
            else:
                done_callback(False, error_traceback)

    thread = threading.Thread(target=thread_target, daemon=daemon)
    thread.start()
    root.after_idle(check)


@copy_type(open)
@contextlib.contextmanager
def backup_open(file: Any, *args: Any, **kwargs: Any) -> Any:
    """Like :func:`open`, but uses a backup file if needed.

    This is useless with modes like ``'r'`` because they don't modify
    the file, but this is useful when overwriting the user's files.

    This needs to be used as a context manager. For example::

        try:
            with utils.backup_open(cool_file, 'w') as file:
                ...
        except (UnicodeError, OSError):
            # log the error and report it to the user

    This automatically restores from the backup on failure.
    """
    path = Path(file)
    if path.exists():
        # there's something to back up
        #
        # for backing up foo.py:
        # if foo-backup.py, then use foo-backup-backup.py etc
        backuppath = path
        while backuppath.exists():
            backuppath = backuppath.with_name(backuppath.stem + "-backup" + backuppath.suffix)

        log.info(f"backing up '{path}' to '{backuppath}'")
        shutil.copy(path, backuppath)

        try:
            yield path.open(*args, **kwargs)
        except Exception as e:
            log.info(f"restoring '{path}' from the backup")
            shutil.move(str(backuppath), str(path))
            raise e
        else:
            log.info(f"deleting '{backuppath}'")
            backuppath.unlink()

    else:
        yield path.open(*args, **kwargs)
