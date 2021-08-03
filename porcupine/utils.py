"""Handy utility functions."""
from __future__ import annotations

import collections
import contextlib
import dataclasses
import functools
import json
import logging
import os
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
from typing import TYPE_CHECKING, Any, Callable, Iterator, TextIO, Type, TypeVar, cast
from urllib.request import url2pathname

import dacite

if sys.version_info >= (3, 9):
    from re import Match
    from typing import Literal
elif sys.version_info >= (3, 8):
    from typing import Literal, Match
else:
    from typing_extensions import Literal
    from typing import Match

import porcupine

log = logging.getLogger(__name__)
_T = TypeVar("_T")


# nsis installs a python to e.g. C:\Users\Akuli\AppData\Local\Porcupine\Python
_installed_with_pynsist = (
    sys.platform == "win32"
    and Path(sys.executable).parent.name.lower() == "python"
    and Path(sys.executable).parent.parent.name.lower() == "porcupine"
)


if sys.platform == "win32":
    # Casting because mypy thinks stdout and stderr can't be None
    if cast(Any, sys).stdout is None and cast(Any, sys).stderr is None:
        # running in pythonw.exe so there's no console window, print still
        # works because it checks if sys.stdout is None
        running_pythonw = True
    elif (
        _installed_with_pynsist
        and sys.stdout is sys.stderr
        and sys.stdout.name is not None  # not sure if necessary
        and Path(sys.stdout.name).parent == Path(os.environ["APPDATA"])
    ):
        # pynsist generates a script that does this:
        #
        #   sys.stdout = sys.stderr = open(blablabla, 'w', **kw)
        #
        # where blablabla is a file directly in %APPDATA%... that's dumb and
        # non-standard imo, and not suitable for porcupine because porcupine
        # takes care of that itself, so... let's undo what it just did
        #
        # TODO: it's possible to write a custom startup script, do that? there
        #       are docs somewhere
        sys.stdout.close()
        os.remove(sys.stdout.name)

        # mypy doesn't know about how std streams can be None
        # https://github.com/python/mypy/issues/8823
        sys.stdout = cast(Any, None)
        sys.stderr = cast(Any, None)

        running_pythonw = True
    else:
        # seems like python was started from e.g. a cmd or powershell
        running_pythonw = False
else:
    running_pythonw = False


python_executable = Path(sys.executable)
if running_pythonw and Path(sys.executable).name.lower() == "pythonw.exe":
    # get rid of the 'w' and hope for the best...
    _possible_python = Path(sys.executable).with_name("python.exe")
    if _possible_python.is_file():
        python_executable = _possible_python


quote: Callable[[str], str]
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


# TODO: document this
def find_project_root(project_file_path: Path) -> Path:
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


# i know, i shouldn't do math with rgb colors, but this is good enough
def invert_color(color: str, *, black_or_white: bool = False) -> str:
    """Return a color with opposite red, green and blue values.

    Example: ``invert_color('white')`` is ``'#000000'`` (black).

    This function uses tkinter for converting the color to RGB. That's
    why a tkinter root window must have been created, but *color* can be
    any Tk-compatible color string, like a color name or a ``'#rrggbb'``
    string. The return value is always a ``'#rrggbb`` string (also compatible
    with Tk).

    If ``black_or_white=True`` is set, then the result is always ``'#000000'``
    (black) or ``'#ffffff'`` (white), depending on whether the color is bright
    or dark.
    """
    # tkinter uses 16-bit colors for some reason, so gotta convert them
    # to 8-bit (with >> 8)
    widget = porcupine.get_main_window()  # any widget would do
    r, g, b = (value >> 8 for value in widget.winfo_rgb(color))

    if black_or_white:
        average = (r + g + b) / 3
        return "#ffffff" if average < 0x80 else "#000000"
    else:
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


def get_children_recursively(
    parent: tkinter.Misc, *, include_parent: bool = False
) -> Iterator[tkinter.Misc]:
    if include_parent:
        yield parent
    for child in parent.winfo_children():
        yield from get_children_recursively(child, include_parent=True)


def _handle_letter(letter: str) -> str:
    if letter.isupper():
        return "Shift-" + letter
    return letter.upper()


# This doesn't handle all possible cases, see bind(3tk)
def _format_binding(binding: str, menu: bool) -> str:
    mac = porcupine.get_main_window().tk.eval("tk windowingsystem") == "aqua"
    parts = binding.lstrip("<").rstrip(">").split("-")

    # don't know how to show click in mac menus
    if mac and menu and any(parts[i : i + 2] == "Button-1".split("-") for i in range(len(parts))):
        return ""

    # <Double-Button-1>  -->  ["double-click"]
    #
    # Do not make parts list longer in loop, otherwise initially calculated
    # range(len(parts)) might be too short
    for i in range(len(parts)):
        if parts[i : i + 3] == ["Double", "Button", "1"]:
            parts[i : i + 3] = ["double-click"]
        elif parts[i : i + 2] == ["Button", "1"]:
            parts[i : i + 2] = ["click"]

    parts = [
        # tk doesn't like e.g. <Control-ö>
        _handle_letter(part) if re.fullmatch(r"[A-Za-z]", part) else part
        for part in parts
    ]
    if "Key" in parts:
        parts.remove("Key")

    if mac:
        # event_info() returns <Mod1-Key-x> for <Command-x>
        parts = [{"Mod1": "Command", "plus": "+", "minus": "-"}.get(part, part) for part in parts]

        if menu:
            # Tk will use the proper symbols automagically, and it expects dash-separated
            # Even "Command--" for command and minus key works
            return "-".join(parts)

        # <ThePhilgrim> I think it's like from left to right... so it would be shift -> ctrl -> alt -> cmd
        parts.sort(
            key=(lambda part: {"Shift": 1, "Control": 2, "Alt": 3, "Command": 4}.get(part, 100))
        )

        parts = [
            {
                "Shift": "⇧",
                "Control": "⌃",  # NOT same as ascii "^"
                "Alt": "⌥",
                "Command": "⌘",
                "Return": "⏎",
            }.get(part, part)
            for part in parts
        ]

        # e.g. "⌘-double-click"
        # But not like this:  ["double-click"] --> ["-double-click"]
        parts[1:] = [
            {"click": "-click", "double-click": "-double-click"}.get(part, part)
            for part in parts[1:]
        ]
        return "".join(parts)

    else:
        parts = [
            {
                "Control": "Ctrl",
                "0": "Zero",  # not needed on mac, its font distinguishes 0 and O well
                "plus": "Plus",
                "minus": "Minus",
                "Return": "Enter",
            }.get(part, part)
            for part in parts
        ]
        return "+".join(parts)


# TODO: document this
def get_binding(virtual_event: str, *, menu: bool = False) -> str:
    bindings = porcupine.get_main_window().event_info(virtual_event)
    if not bindings and not menu:
        log.warning(f"no bindings configured for {virtual_event}")
    return _format_binding(bindings[0], menu) if bindings else ""


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


def errordialog(title: str, message: str, monospace_text: str | None = None) -> None:
    """This is a lot like ``tkinter.messagebox.showerror``.

    This function can be called with or without creating a root window
    first. If *monospace_text* is not None, it will be displayed below
    the message in a ``tkinter.Text`` widget.

    Example::

        try:
            do something
        except SomeError:
            utils.errordialog("Oh no", "Doing something failed!",
                              traceback.format_exc())
    """
    window = tkinter.Toplevel()
    window.transient(porcupine.get_main_window())

    # there's nothing but this frame in the window because ttk widgets
    # may use a different background color than the window
    big_frame = ttk.Frame(window)
    big_frame.pack(fill="both", expand=True)

    label = ttk.Label(big_frame, text=message)

    if monospace_text is None:
        label.pack(fill="both", expand=True)
        geometry = "250x150"
    else:
        label.pack(anchor="center")
        # there's no ttk.Text 0_o this looks very different from
        # everything else and it sucks :(
        text = tkinter.Text(big_frame, width=1, height=1)
        text.pack(fill="both", expand=True)
        text.insert("1.0", monospace_text)
        text.config(state="disabled")
        geometry = "400x300"

    button = ttk.Button(big_frame, text="OK", command=window.destroy)
    button.pack(pady=10)
    button.focus()
    button.bind("<Return>", (lambda event: button.invoke()), add=True)  # type: ignore[no-untyped-call]

    window.title(title)
    window.geometry(geometry)
    window.wait_window()


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


# how to type hint context manager: https://stackoverflow.com/a/49736916
@contextlib.contextmanager
def backup_open(path: Path, *args: Any, **kwargs: Any) -> Iterator[TextIO]:
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
