"""Handy utility functions."""
from __future__ import annotations

import collections
import contextlib
import dataclasses
import functools
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import tkinter
import traceback
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Callable, Deque, Dict, Iterator, Optional, TextIO, Type, TypeVar, Union, cast

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
_T = TypeVar('_T')
BreakOrNone = Optional[Literal['break']]


# nsis installs a python to e.g. C:\Users\Akuli\AppData\Local\Porcupine\Python
_installed_with_pynsist = (
    sys.platform == 'win32' and
    pathlib.Path(sys.executable).parent.name.lower() == 'python' and
    pathlib.Path(sys.executable).parent.parent.name.lower() == 'porcupine')


if sys.platform == 'win32':
    if sys.stdout is None and sys.stderr is None:
        # running in pythonw.exe so there's no console window, print still
        # works because it checks if sys.stdout is None
        running_pythonw = True
    elif (_installed_with_pynsist and
          sys.stdout is sys.stderr and
          sys.stdout.name is not None and       # not sure if necessary
          pathlib.Path(sys.stdout.name).parent == pathlib.Path(os.environ['APPDATA'])):
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


python_executable = pathlib.Path(sys.executable)
if running_pythonw and pathlib.Path(sys.executable).name.lower() == 'pythonw.exe':
    # get rid of the 'w' and hope for the best...
    _possible_python = pathlib.Path(sys.executable).with_name('python.exe')
    if _possible_python.is_file():
        python_executable = _possible_python


quote: Callable[[str], str]
if sys.platform == 'win32':
    # this is mostly copy/pasted from subprocess.list2cmdline
    def quote(string: str) -> str:
        result = []
        needquote = False
        bs_buf = []

        needquote = (" " in string) or ("\t" in string) or not string
        if needquote:
            result.append('"')

        for c in string:
            if c == '\\':
                # Don't know if we need to double yet.
                bs_buf.append(c)
            elif c == '"':
                # Double backslashes.
                result.append('\\' * len(bs_buf)*2)
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

        return ''.join(result)

else:
    from shlex import quote
    quote = quote       # silence pyflakes warning


# Using these with subprocess prevents opening unnecessary cmd windows
# TODO: document this
subprocess_kwargs: Dict[str, Any] = {}
if sys.platform == 'win32':
    # https://stackoverflow.com/a/1813893
    subprocess_kwargs['startupinfo'] = subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW)


_LIKELY_PROJECT_ROOT_THINGS = ['.editorconfig'] + [
    readme + extension
    for readme in ['README', 'readme', 'Readme', 'ReadMe']
    for extension in ['', '.txt', '.md', '.rst']
]


# TODO: document this
def find_project_root(project_file_path: pathlib.Path) -> pathlib.Path:
    assert project_file_path.is_absolute()

    likely_root = None
    for path in project_file_path.parents:
        if (path / '.git').exists():
            return path   # trust this the most, if it exists
        elif likely_root is None and any((path / thing).exists() for thing in _LIKELY_PROJECT_ROOT_THINGS):
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
    widget = porcupine.get_main_window()    # any widget would do
    r, g, b = (value >> 8 for value in widget.winfo_rgb(color))

    if black_or_white:
        average = (r + g + b)/3
        return '#ffffff' if average < 0x80 else '#000000'
    else:
        return '#%02x%02x%02x' % (0xff - r, 0xff - g, 0xff - b)


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
        round(color1_amount*value1 + color2_amount*value2)
        for value1, value2 in zip(widget.winfo_rgb(color1), widget.winfo_rgb(color2))
    )
    return '#%02x%02x%02x' % (r >> 8, g >> 8, b >> 8)  # convert back to 8-bit


def get_children_recursively(parent: tkinter.Misc, *, include_parent: bool = False) -> Iterator[tkinter.Misc]:
    if include_parent:
        yield parent
    for child in parent.winfo_children():
        yield from get_children_recursively(child, include_parent=True)


class _TooltipManager:

    # This needs to be shared by all instances because there's only one
    # mouse pointer.
    tipwindow = None

    def __init__(self, widget: tkinter.Widget, text: str) -> None:
        widget.bind('<Enter>', self.enter, add=True)
        widget.bind('<Leave>', self.leave, add=True)
        widget.bind('<Motion>', self.motion, add=True)
        self.widget = widget
        self.got_mouse = False
        self.text = text    # can be changed after creating tooltip manager

    @classmethod
    def destroy_tipwindow(
            cls, junk_event: Optional[tkinter.Event[tkinter.Misc]] = None) -> None:
        if cls.tipwindow is not None:
            cls.tipwindow.destroy()
            cls.tipwindow = None

    def enter(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # For some reason, toplevels get also notified of their
        # childrens' events.
        if event.widget is self.widget:
            self.destroy_tipwindow()
            self.got_mouse = True
            self.widget.after(1000, self.show)

    def leave(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if event.widget is self.widget:
            self.destroy_tipwindow()
            self.got_mouse = False

    def motion(self, event: tkinter.Event[tkinter.Misc]) -> None:
        self.mousex = event.x_root
        self.mousey = event.y_root

    def show(self) -> None:
        if self.got_mouse:
            self.destroy_tipwindow()
            tipwindow = type(self).tipwindow = tkinter.Toplevel()
            tipwindow.geometry(f'+{self.mousex + 10}+{self.mousey - 10}')
            tipwindow.bind('<Motion>', self.destroy_tipwindow, add=True)
            tipwindow.overrideredirect(True)

            # If you modify this, make sure to always define either no
            # colors at all or both foreground and background. Otherwise
            # the label will have light text on a light background or
            # dark text on a dark background on some systems.
            tkinter.Label(tipwindow, text=self.text, border=3,
                          fg='black', bg='white').pack()


def set_tooltip(widget: tkinter.Widget, text: str) -> None:
    """A simple tooltip implementation with tkinter.

    After calling ``set_tooltip(some_widget, "hello")``, "hello" will be
    displayed in a small window when the user moves the mouse over the
    widget and waits for 1 second.

    If you have read some of IDLE's source code (if you haven't, that's
    good; IDLE's source code is ugly), you might be wondering what this
    thing has to do with ``idlelib/tooltip.py``. Don't worry, I didn't
    copy/paste any code from idlelib and I didn't read idlelib while I
    wrote the tooltip code! Idlelib is awful and I don't want to use
    anything from it in my editor.
    """
    try:
        manager: _TooltipManager = cast(Any, widget)._tooltip_manager
    except AttributeError:
        cast(Any, widget)._tooltip_manager = _TooltipManager(widget, text)
        return
    manager.text = text


def _handle_letter(match: Match[str]) -> str:
    if match.group(0).isupper():
        return 'Shift-' + match.group(0)
    return match.group(0).upper()


def _format_binding(binding: str, menu: bool) -> str:
    # this doesn't handle all possible cases, see bind(3tk)
    mac = (porcupine.get_main_window().tk.call('tk', 'windowingsystem') == 'aqua')
    binding = binding.lstrip('<').rstrip('>')

    # don't know how to show click in mac menus
    if mac and menu and re.search(r'\bButton-1\b', binding):
        return ''

    binding = re.sub(r'\bButton-1\b', 'click', binding)
    binding = re.sub(r'\b[A-Za-z]\b', _handle_letter, binding)  # tk doesn't like e.g. <Control-ö>
    binding = re.sub(r'\bKey-', '', binding)
    if mac:
        binding = re.sub(r'\bMod1\b', 'Command', binding)  # event_info() returns <Mod1-Key-x> for <Command-x>
        binding = re.sub(r'\bplus\b', '+', binding)
        binding = re.sub(r'\bminus\b', '-', binding)   # e.g. "Command-minus" --> "Command--"

        if menu:
            # Tk will use the proper symbols automagically, and it expects dash-separated
            return binding

        binding = re.sub(r'\bReturn\b', r'⏎', binding)

        # <ThePhilgrim> I think it's like from left to right... so it would be shift -> ctrl -> alt -> cmd
        # We need to sub backwards, because each sub puts its thing before everything else
        binding = re.sub(r'^(.*)\bCommand-', r'⌘-\1', binding)
        binding = re.sub(r'^(.*)\bAlt-', r'⌥-\1', binding)
        binding = re.sub(r'^(.*)\bControl-', r'⌃-\1', binding)   # look carefully, two different kinds of hats
        binding = re.sub(r'^(.*)\bShift-', r'⇧-\1', binding)

        # "Command--" --> "Command-"
        # "Command-+" --> "Command+"
        binding = re.sub(r'-(-?)', r'\1', binding)

        # e.g. ⌘-click
        return binding.replace('click', '-click')

    else:
        binding = re.sub(r'\bControl\b', 'Ctrl', binding)
        binding = re.sub(r'\b0\b', 'Zero', binding)   # most fonts don't distinguishes O and 0 nicely, mac font does
        binding = re.sub(r'\bplus\b', 'Plus', binding)
        binding = re.sub(r'\bminus\b', 'Minus', binding)
        binding = re.sub(r'\bReturn\b', 'Enter', binding)
        return binding.replace('-', '+')


# TODO: document this
def get_binding(virtual_event: str, *, menu: bool = False) -> str:
    bindings = porcupine.get_main_window().event_info(virtual_event)
    if not bindings and not menu:
        log.warning(f"no bindings configured for {virtual_event}")
    return _format_binding(bindings[0], menu) if bindings else ''


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

    def data_widget(self) -> tkinter.Misc:
        """
        If a widget was passed as ``data`` to ``event_generate()``, then this
        returns that widget. Otherwise this raises an error.

        Note that ``event.widget`` is the widget whose ``event_generate()``
        method was used while ``event.data_widget()`` is the ``data`` argument
        of ``widget.event_generate(..., data=the_data_widget)``. Usually these
        are different widgets; if they are known to be the same widget, then
        you probably don't need :func:`bind_with_data` at all.
        """
        return self.widget.nametowidget(self.data_string)

    def data_class(self, T: Type[_T]) -> _T:
        """
        If a dataclass instance of type ``T`` was passed as ``data`` to
        ``event_generate()``, then this returns a copy of it. Otherwise this
        raises an error.

        ``T`` must be a dataclass that inherits from :class:`EventDataclass`.
        """
        assert self.data_string.startswith(T.__name__ + '{')
        result = dacite.from_dict(T, json.loads(self.data_string[len(T.__name__):]))
        assert isinstance(result, T)
        return result

    def __repr__(self) -> str:
        match = re.fullmatch(r'<(.*)>', super().__repr__())
        assert match is not None
        return f'<{match.group(1)} data_string={self.data_string!r}>'


def bind_with_data(
        widget: tkinter.Misc,
        sequence: str,
        callback: Callable[[EventWithData], Optional[str]],
        add: bool = False) -> str:
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
    event_objects: Deque[Union[tkinter.Event[tkinter.Misc], EventWithData]] = collections.deque()
    widget.bind(sequence, event_objects.append, add=add)

    def run_the_callback(data_string: str) -> Optional[str]:
        event = event_objects.popleft()
        event.__class__ = EventWithData    # evil haxor muhaha
        assert isinstance(event, EventWithData)
        event.data_string = data_string
        return callback(event)      # may return 'break'

    # tkinter's bind() ignores the add argument when the callback is a
    # string :(
    funcname = widget.register(run_the_callback)
    widget.tk.eval(
        'bind %s %s {+ if {"[%s %%d]" == "break"} break }'
        % (widget, sequence, funcname))
    return funcname


def add_scroll_command(
        widget: tkinter.Text,
        option: Literal['xscrollcommand', 'yscrollcommand'],
        callback: Callable[[], None]) -> None:
    """Schedule ``callback`` to run with no arguments when ``widget`` is scrolled.

    The option should be ``'xscrollcommand'`` for horizontal scrolling or
    ``'yscrollcommand'`` for vertical scrolling.

    Unlike when setting the option directly, this function can be called
    multiple times with the same widget and the same option to set multiple
    callbacks.
    """
    if not widget[option]:
        widget[option] = (lambda *args: None)
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
    widget[option] = widget.register(callback) + '\n' + tcl_code


class TemporaryBind:
    """Bind and unbind a callback.

    It's possible (and in Porcupine plugins, highly recommended) to use
    ``add=True`` when binding. This way more than one function can be
    bound to the same key sequence at the same time.

    Unfortunately tkinter provodes no good way to unbind functions bound
    with ``add=True`` one by one, and the ``unbind()`` method always
    unbinds *everything* (see the source code). This function only
    unbinds the function it bound, and doesn't touch anything else.

    Use this as a context manager, like this::

        with utils.TemporaryBind(some_widget, '<Button-1>', on_click):
            # now clicking the widget runs on_click() and whatever was
            # bound before (unless on_click() returns 'break')
            ...
        # now on_click() doesn't run when the widget is clicked, but
        # everything else still runs

    Or call the ``.unbind()`` method when you want to::

        binding = utils.TemporaryBind(...)
        ...
        binding.unbind()

    Calls to this function may be nested, and other things can be bound
    inside the ``with`` block as long as ``add=True`` is used.

    The event objects are just like with :func:`bind_with_data`.
    """

    def __init__(self, widget: tkinter.Misc, sequence: str, func: Callable[[EventWithData], BreakOrNone]) -> None:
        self._widget = widget
        self._sequence = sequence

        not_bound_commands = widget.bind(sequence)
        self._tcl_command = bind_with_data(widget, sequence, func, add=True)
        bound_commands = widget.bind(sequence)
        assert bound_commands.startswith(not_bound_commands)
        self._new_things = bound_commands[len(not_bound_commands):]

    def unbind(self) -> None:
        # other stuff might be bound too while this thing was yielding
        try:
            bound_and_stuff = self._widget.bind(self._sequence)
        except tkinter.TclError as e:
            if self._widget.winfo_exists():
                raise e
            else:
                # widget is already destroyed, no need to do anything
                return

        assert bound_and_stuff.count(self._new_things) == 1
        self._widget.bind(self._sequence, bound_and_stuff.replace(self._new_things, ''))  # bindcheck: ignore

        # tkinter's unbind() does this too to avoid memory leaks
        self._widget.deletecommand(self._tcl_command)

    def __enter__(self) -> None:
        pass

    def __exit__(self, *error: object) -> None:
        self.unbind()


# this is not bind_tab to avoid confusing with tabs.py, as in browser tabs
def bind_tab_key(
        widget: tkinter.Widget,
        on_tab: Callable[['tkinter.Event[Any]', bool], BreakOrNone],
        **bind_kwargs: Any) -> None:
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
    def callback(shifted: bool, event: tkinter.Event[tkinter.Misc]) -> BreakOrNone:
        return on_tab(event, shifted)

    if widget.tk.call('tk', 'windowingsystem') == 'x11':
        # even though the event keysym says Left, holding down the right
        # shift and pressing tab also works :D
        shift_tab = '<ISO_Left_Tab>'
    else:
        shift_tab = '<Shift-Tab>'

    widget.bind('<Tab>', functools.partial(callback, False), **bind_kwargs)   # bindcheck: ignore
    widget.bind(shift_tab, functools.partial(callback, True), **bind_kwargs)  # bindcheck: ignore


def errordialog(title: str, message: str,
                monospace_text: Optional[str] = None) -> None:
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
    big_frame.pack(fill='both', expand=True)

    label = ttk.Label(big_frame, text=message)

    if monospace_text is None:
        label.pack(fill='both', expand=True)
        geometry = '250x150'
    else:
        label.pack(anchor='center')
        # there's no ttk.Text 0_o this looks very different from
        # everything else and it sucks :(
        text = tkinter.Text(big_frame, width=1, height=1)
        text.pack(fill='both', expand=True)
        text.insert('1.0', monospace_text)
        text.config(state='disabled')
        geometry = '400x300'

    button = ttk.Button(big_frame, text="OK", command=window.destroy)
    button.pack(pady=10)
    button.focus()
    button.bind('<Return>', (lambda event: button.invoke()), add=True)

    window.title(title)
    window.geometry(geometry)
    window.wait_window()


def run_in_thread(
    blocking_function: Callable[[], _T],
    done_callback: Callable[[bool, Union[str, _T]], None],
    *,
    check_interval_ms: int = 100,
    daemon: bool = False,
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

    As with :class:`threading.Thread`, set ``daemon=True`` to use a daemon
    thread. Then the thread will end forcefully when Porcupine exits, so
    Porcupine will exit even if the thread gets stuck, but the thread might not
    get a chance to finish whatever it is doing.
    """
    root = porcupine.get_main_window()  # any widget would do

    value: _T
    error_traceback: Optional[str] = None

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

    thread = threading.Thread(target=thread_target, name='run_in_thread_' + str(locals()), daemon=daemon)
    thread.start()
    root.after_idle(check)


# how to type hint context manager: https://stackoverflow.com/a/49736916
@contextlib.contextmanager
def backup_open(path: pathlib.Path, *args: Any, **kwargs: Any) -> Iterator[TextIO]:
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
            backuppath = backuppath.with_name(
                backuppath.stem + '-backup' + backuppath.suffix)

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
