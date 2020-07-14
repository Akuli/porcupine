"""Handy utility functions."""

import collections
import contextlib
import functools
import json
import logging
import os
import pathlib
import platform
import re
import shutil
import string as string_module      # string is used as a variable name
import subprocess
import sys
import threading
import tkinter
from tkinter import ttk
import traceback
import typing

import porcupine

log = logging.getLogger(__name__)


# runtime will work on python < 3.8, mypy won't
if typing.TYPE_CHECKING:
    # python 3.8 feature
    BreakOrNone = typing.Optional[typing.Literal['break']]
else:
    BreakOrNone = object


# nsis installs a python to e.g. C:\Users\Akuli\AppData\Local\Porcupine\Python
_installed_with_pynsist = (
    platform.system() == 'Windows' and
    pathlib.Path(sys.executable).parent.name.lower() == 'python' and
    pathlib.Path(sys.executable).parent.parent.name.lower() == 'porcupine')


if platform.system() == 'Windows':
    running_pythonw = True
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
        sys.stdout = None   # type: ignore
        sys.stderr = None   # type: ignore

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


def _find_short_python() -> str:
    if platform.system() == 'Windows':
        # windows python uses a py.exe launcher program in system32
        expected = 'Python %d.%d.%d' % sys.version_info[:3]

        try:
            for python in ['py', 'py -%d' % sys.version_info[0],
                           'py -%d.%d' % sys.version_info[:2]]:
                # command strings aren't different from lists of
                # arguments on windows, the subprocess module just
                # quotes lists anyway (see subprocess.list2cmdline)
                got = subprocess.check_output('%s --version' % python)
                if expected.encode('ascii') == got.strip():
                    return python
        except (OSError, subprocess.CalledProcessError):
            # something's wrong with py.exe 0_o it probably doesn't
            # exist at all and we got a FileNotFoundError
            pass

    else:
        for python in ['python', 'python%d' % sys.version_info[0],
                       'python%d.%d' % sys.version_info[:2]]:
            # samefile() does the right thing with symlinks
            path_string = shutil.which(python)
            if (path_string is not None and
                    os.path.samefile(path_string, sys.executable)):
                return python

    # use the full path as a fallback
    return str(python_executable)


short_python_command: str = _find_short_python()


quote: typing.Callable[[str], str]
if platform.system() == 'Windows':
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
                result.append('\\' * len(bs_buf)*2)     # noqa
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
    from shlex import quote     # noqa


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


def mix_colors(color1: str, color2: str) -> str:
    widget = porcupine.get_main_window()    # any widget would do
    r, g, b = (
        sum(pair) // 2     # average
        for pair in zip(widget.winfo_rgb(color1), widget.winfo_rgb(color2))
    )
    return '#%02x%02x%02x' % (r >> 8, g >> 8, b >> 8)


class _TooltipManager:

    # This needs to be shared by all instances because there's only one
    # mouse pointer.
    tipwindow = None

    def __init__(self, widget: tkinter.Widget) -> None:
        widget.bind('<Enter>', self.enter, add=True)
        widget.bind('<Leave>', self.leave, add=True)
        widget.bind('<Motion>', self.motion, add=True)
        self.widget = widget
        self.got_mouse = False
        self.text: typing.Optional[str] = None

    @classmethod
    def destroy_tipwindow(
            cls, junk_event: typing.Optional[tkinter.Event] = None) -> None:
        if cls.tipwindow is not None:
            cls.tipwindow.destroy()
            cls.tipwindow = None

    def enter(self, event: tkinter.Event) -> None:
        # For some reason, toplevels get also notified of their
        # childrens' events.
        if event.widget is self.widget:
            self.destroy_tipwindow()
            self.got_mouse = True
            self.widget.after(1000, self.show)

    def leave(self, event: tkinter.Event) -> None:
        if event.widget is self.widget:
            self.destroy_tipwindow()
            self.got_mouse = False

    def motion(self, event: tkinter.Event) -> None:
        self.mousex = event.x_root
        self.mousey = event.y_root

    def show(self) -> None:
        if not self.got_mouse:
            return

        self.destroy_tipwindow()
        if self.text is not None:
            tipwindow = type(self).tipwindow = tkinter.Toplevel()
            tipwindow.geometry('+%d+%d' % (self.mousex+10, self.mousey-10))
            tipwindow.bind('<Motion>', self.destroy_tipwindow)
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
    widget and waits for 1 second. Do ``set_tooltip(some_widget, None)``
    to get rid of a tooltip.

    If you have read some of IDLE's source code (if you haven't, that's
    good; IDLE's source code is ugly), you might be wondering what this
    thing has to do with ``idlelib/tooltip.py``. Don't worry, I didn't
    copy/paste any code from idlelib and I didn't read idlelib while I
    wrote the tooltip code! Idlelib is awful and I don't want to use
    anything from it in my editor.
    """

    try:
        manager: _TooltipManager = (
            typing.cast(typing.Any, widget)._tooltip_manager)
    except AttributeError:
        if text is None:
            return
        manager = _TooltipManager(widget)
        typing.cast(typing.Any, widget)._tooltip_manager = manager

    manager.text = text


# this is documented in bind_with_data()
#
# TODO: mention this in docs, useful for mypy
class EventWithData(tkinter.Event):

    data_string: str

    def data_widget(self) -> tkinter.BaseWidget:
        return self.widget.nametowidget(self.data_string)

    def data_json(self) -> typing.Any:
        return json.loads(self.data_string)

    def __repr__(self) -> str:
        match = re.fullmatch(r'<(.*)>', super().__repr__())
        assert match is not None
        return '<%s data_string=%r>' % (match.group(1), self.data_string)


def bind_with_data(
        widget: tkinter.BaseWidget,
        sequence: str,
        callback: typing.Callable[[EventWithData], typing.Optional[str]],
        add: bool = False) -> str:
    """
    Like ``widget.bind(sequence, callback)``, but supports the ``data``
    argument of ``event_generate()``.

    Here's an example::

        from porcupine import utils

        def on_wutwut(event: utils.EventWithData):
            print(event.data_string)

        utils.bind_with_data(some_widget, '<<Thingy>>', on_wutwut, add=True)

        # this prints 'wut wut'
        some_widget.event_generate('<<Thingy>>', data='wut wut')

    Note that everything is a string in Tcl, so tkinter ``str()``'s the data.

    The event objects have all the attributes that tkinter events
    usually have, and these additional attributes and methods:

        ``data_string``
            See the above example.

        ``data_widget()``
            If a widget was passed as ``data`` to ``event_generate()``,
            then this returns that widget.

        ``data_json()``
            If ``json.dumps(something)`` was passed as ``data`` to
            ``event_generate()``, then this returns the parsed JSON.
    """
    # tkinter creates event objects normally and appends them to the
    # deque, then run_callback() adds data_blablabla attributes to the
    # event objects and runs callback(event)
    #
    # TODO: is it possible to do this without a deque?
    event_objects: typing.Deque[
        typing.Union[tkinter.Event, EventWithData]] = collections.deque()
    widget.bind(sequence, event_objects.append, add=add)
    # TODO: does the above bind get ever unbound so that it doesn't leak? see
    #       tkinter's unbind method

    def run_the_callback(data_string: str) -> typing.Optional[str]:
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


# TODO: document this
def forward_event(event_name: str, from_: tkinter.Widget, to: tkinter.Widget,
                  *, add: bool = True) -> str:
    def callback(event: tkinter.Event) -> None:
        # make the coordinates relative to the 'to' widget
        x = event.x_root - to.winfo_rootx()
        y = event.y_root - to.winfo_rooty()
        # no need to specify rootx and rooty, because Tk can calculate them

        if isinstance(event, EventWithData):
            to.event_generate(event_name, x=x, y=y, data=event.data_string)
        else:
            to.event_generate(event_name, x=x, y=y)

    if event_name.startswith('<<'):
        # virtual events support data
        return bind_with_data(from_, event_name, callback, add=add)
    else:
        return from_.bind(event_name, callback, add=add)


@contextlib.contextmanager
def temporary_bind(
    widget: tkinter.BaseWidget,
    sequence: str,
    func: typing.Callable[[tkinter.Event], typing.Optional[str]]
) -> typing.Iterator[None]:
    """Bind and unbind a callback.

    It's possible (and in Porcupine plugins, highly recommended) to use
    ``add=True`` when binding. This way more than one function can be
    bound to the same key sequence at the same time.

    Unfortunately tkinter provodes no good way to unbind functions bound
    with ``add=True`` one by one, and the ``unbind()`` method always
    unbinds *everything* (see the source code). This function only
    unbinds the function it bound, and doesn't touch anything else.

    Use this as a context manager, like this::

        with utils.temporary_bind(some_widget, '<Button-1>', on_click):
            # now clicking the widget runs on_click() and whatever was
            # bound before (unless on_click() returns 'break')
            ...
        # now on_click() doesn't run when the widget is clicked, but
        # everything else still runs

    Calls to this function may be nested, and other things can be bound
    inside the ``with`` block as long as ``add=True`` is used.

    The event objects support the same additional attributes as those
    from :func:`bind_with_data`.
    """
    not_bound_commands = widget.bind(sequence)
    tcl_command = bind_with_data(widget, sequence, func, add=True)
    bound_commands = widget.bind(sequence)
    assert bound_commands.startswith(not_bound_commands)
    new_things = bound_commands[len(not_bound_commands):]

    try:
        yield
    finally:
        # other stuff might be bound too while this thing was yielding
        bound_and_stuff = widget.bind(sequence)
        assert bound_and_stuff.count(new_things) == 1
        widget.bind(sequence, bound_and_stuff.replace(new_things, ''))

        # unbind() does this too to avoid memory leaks
        widget.deletecommand(tcl_command)


# this is not bind_tab to avoid confusing with tabs.py, as in browser tabs
def bind_tab_key(
        widget: tkinter.Widget,
        on_tab: typing.Callable[[tkinter.Event, bool], BreakOrNone],
        **bind_kwargs: typing.Any) -> None:
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
    def callback(shifted: bool, event: tkinter.Event) -> BreakOrNone:
        return on_tab(event, shifted)

    if widget.tk.call('tk', 'windowingsystem') == 'x11':
        # even though the event keysym says Left, holding down the right
        # shift and pressing tab also works :D
        shift_tab = '<ISO_Left_Tab>'
    else:
        shift_tab = '<Shift-Tab>'

    widget.bind('<Tab>', functools.partial(callback, False), **bind_kwargs)
    widget.bind(shift_tab, functools.partial(callback, True), **bind_kwargs)


def bind_mouse_wheel(
        widget: tkinter.Widget,
        callback: typing.Callable[[str], None],
        *,
        prefixes: str = '',
        **bind_kwargs: typing.Any) -> None:
    """Bind mouse wheel events to callback.

    The callback will be called like ``callback(direction)`` where
    *direction* is ``'up'`` or ``'down'``. The *prefixes* argument can
    be used to change the binding string. For example,
    ``prefixes='Control-'`` means that callback will be ran when the
    user holds down Control and rolls the wheel.

    .. note::
        This function has not been tested on OSX. If you have a Mac,
        please try it out and let me know how much it sucked.
    """
    # i needed to cheat and use stackoverflow for the mac stuff :(
    # http://stackoverflow.com/a/17457843
    if widget.tk.call('tk', 'windowingsystem') == 'x11':
        def real_callback(event: tkinter.Event) -> None:
            callback('up' if event.num == 4 else 'down')

        widget.bind('<{}Button-4>'.format(prefixes),
                    real_callback, **bind_kwargs)
        widget.bind('<{}Button-5>'.format(prefixes),
                    real_callback, **bind_kwargs)

    else:
        # TODO: test this on OSX
        def real_callback(event: tkinter.Event) -> None:
            callback('up' if event.delta > 0 else 'down')

        widget.bind('<{}MouseWheel>'.format(prefixes),
                    real_callback, **bind_kwargs)


# TODO: document this
def create_passive_text_widget(
        parent: tkinter.Widget, **kwargs: typing.Any) -> tkinter.Text:
    kwargs.setdefault('font', 'TkDefaultFont')
    kwargs.setdefault('borderwidth', 0)
    kwargs.setdefault('relief', 'flat')
    kwargs.setdefault('wrap', 'word')       # TODO: remember to mention in docs
    kwargs.setdefault('state', 'disabled')  # TODO: remember to mention in docs
    text = tkinter.Text(parent, **kwargs)

    def update_colors(junk: typing.Optional[tkinter.Event] = None) -> None:
        # tkinter's ttk::style api sucks so let's not use it
        ttk_fg = text.tk.eval('ttk::style lookup TLabel.label -foreground')
        ttk_bg = text.tk.eval('ttk::style lookup TLabel.label -background')

        if not ttk_fg and not ttk_bg:
            # stupid ttk theme, it deserves this
            ttk_fg = 'black'
            ttk_bg = 'white'
        elif not ttk_bg:
            # this happens with e.g. elegance theme (more_plugins/ttkthemes.py)
            ttk_bg = invert_color(ttk_fg, black_or_white=True)
        elif not ttk_fg:
            ttk_fg = invert_color(ttk_bg, black_or_white=True)

        text['foreground'] = ttk_fg
        text['background'] = ttk_bg
        text['highlightbackground'] = ttk_bg

    # even non-ttk widgets can handle <<ThemeChanged>>
    # TODO: make sure that this works
    text.bind('<<ThemeChanged>>', update_colors)
    update_colors()

    return text


try:
    Spinbox = ttk.Spinbox
except AttributeError:
    # python 3.6 compat thing, written similarly to ttk.Combobox
    class Spinbox(ttk.Entry):   # type: ignore

        def __init__(self, master, *, from_=None, **kwargs):     # type: ignore
            if from_ is not None:
                kwargs['from'] = from_  # this actually works
            super().__init__(master, 'ttk::spinbox', **kwargs)  # type: ignore

        def configure(self, *args, **kwargs):   # type: ignore
            if 'from_' in kwargs:
                kwargs['from'] = kwargs.pop('from_')
            return super().configure(*args, **kwargs)   # type: ignore

        config = configure


def errordialog(title: str, message: str,
                monospace_text: typing.Optional[str] = None) -> None:
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
    root = porcupine.get_main_window()
    if root is None:
        window = tkinter.Tk()
    else:
        window = tkinter.Toplevel()
        window.transient(root)

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
        text['state'] = 'disabled'
        geometry = '400x300'

    button = ttk.Button(big_frame, text="OK", command=window.destroy)
    button.pack(pady=10)

    window.title(title)
    window.geometry(geometry)
    window.wait_window()


T = typing.TypeVar('T')


def run_in_thread(
    blocking_function: typing.Callable[[], T],
    done_callback: typing.Callable[[bool, typing.Union[str, T]], None],
) -> None:
    """Run ``blocking_function()`` in another thread.

    If the *blocking_function* raises an error,
    ``done_callback(False, traceback)`` will be called where *traceback*
    is the error message as a string. If no errors are raised,
    ``done_callback(True, result)`` will be called where *result* is the
    return value from *blocking_function*. The *done_callback* is always
    called from Tk's main loop, so it can do things with Tkinter widgets
    unlike *blocking_function*.
    """
    root = porcupine.get_main_window()  # any widget would do

    value: T
    error_traceback: typing.Optional[str] = None

    def thread_target() -> None:
        nonlocal value
        nonlocal error_traceback

        # the logging module uses locks so calling it from another
        # thread should be safe
        try:
            value = blocking_function()
        except Exception:
            error_traceback = traceback.format_exc()

    def check() -> None:
        if thread.is_alive():
            # let's come back and check again later
            root.after(100, check)
        else:
            if error_traceback is None:
                done_callback(True, value)
            else:
                done_callback(False, error_traceback)

    thread = threading.Thread(target=thread_target)
    thread.start()
    root.after_idle(check)


# how to type hint context manager: https://stackoverflow.com/a/49736916
@contextlib.contextmanager
def backup_open(
    path: pathlib.Path,
    *args: typing.Any, **kwargs: typing.Any,
) -> typing.Iterator[typing.TextIO]:
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


def get_keyboard_shortcut(binding: str) -> str:
    """Convert a Tk binding string to a format that most people are used to.

    >>> get_keyboard_shortcut('<Control-c>')
    'Ctrl+C'
    >>> get_keyboard_shortcut('<Control-C>')
    'Ctrl+Shift+C'
    >>> get_keyboard_shortcut('<Control-0>')
    'Ctrl+Zero'
    >>> get_keyboard_shortcut('<Control-1>')
    'Ctrl+1'
    >>> get_keyboard_shortcut('<F11>')
    'F11'
    """
    # TODO: handle more corner cases? see bind(3tk)
    parts = binding.lstrip('<').rstrip('>').split('-')
    result = []

    for part in parts:
        if part == 'Control':
            # TODO: i think this is supposed to use the command symbol
            # on OSX? i don't have a mac
            result.append('Ctrl')
        # tk doesnt like e.g. <Control-ö> :( that's why ascii only here
        elif len(part) == 1 and part in string_module.ascii_lowercase:
            result.append(part.upper())
        elif len(part) == 1 and part in string_module.ascii_uppercase:
            result.append('Shift')
            result.append(part)
        elif part == '0':
            # 0 and O look too much like each other
            result.append('Zero')
        else:
            # good enough guess :D
            result.append(part.capitalize())

    return '+'.join(result)
