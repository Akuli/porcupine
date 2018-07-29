"""Handy utility functions."""

import collections
import contextlib
import functools
import logging
import os
import platform
import shlex
import shutil
import string as string_module      # string is used as a variable name
import subprocess
import sys
import threading
import tkinter
from tkinter import ttk
import traceback

import porcupine

log = logging.getLogger(__name__)


# nsis installs a python to e.g. C:\Users\Akuli\AppData\Local\Porcupine\Python
# TODO: document this
_installed_with_pynsist = (
    platform.system() == 'Windows' and
    os.path.dirname(sys.executable).lower().endswith(r'\porcupine\python'))


if platform.system() == 'Windows':
    running_pythonw = True
    if sys.stdout is None and sys.stderr is None:
        # running in pythonw.exe so there's no console window, print still
        # works because it checks if sys.stdout is None
        running_pythonw = True
    elif (_installed_with_pynsist and
          sys.stdout is sys.stderr and
          isinstance(sys.stdout.name, str) and   # not sure if it can be None
          os.path.dirname(sys.stdout.name) == os.environ['APPDATA']):
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
        sys.stdout = None
        sys.stderr = None
    else:
        # seems like python was started from e.g. a cmd or powershell
        running_pythonw = False
else:
    running_pythonw = False


python_executable = sys.executable
if running_pythonw and sys.executable.lower().endswith(r'\pythonw.exe'):
    # get rid of the 'w' and hope for the best...
    _possible_python = sys.executable[:-5] + sys.executable[-4:]
    if os.path.isfile(_possible_python):
        python_executable = _possible_python


def _find_short_python():
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
            # os.path.samefile() does the right thing with symlinks
            path = shutil.which(python)
            if path is not None and os.path.samefile(path, sys.executable):
                return python

    # use the full path as a fallback
    return python_executable


short_python_command = _find_short_python()


if platform.system() == 'Windows':
    # this is mostly copy/pasted from subprocess.list2cmdline
    def quote(string):
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
    def quote(string):
        return shlex.quote(string)


def invert_color(color):
    """Return a color with opposite red, green and blue values.

    Example: ``invert_color('white')`` is ``'#000000'`` (black).

    This function uses tkinter for converting the color to RGB. That's
    why a tkinter root window must have been created, but *color* can be
    any Tk-compatible color string, like a color name or a ``'#rrggbb'``
    string.

    The return value is always a ``'#rrggbb`` string (also compatible
    with Tk).
    """
    # tkinter uses 16-bit colors for some reason, so gotta convert them
    # to 8-bit (with >> 8)
    widget = porcupine.get_main_window()
    r, g, b = (0xff - (value >> 8) for value in widget.winfo_rgb(color))
    return '#%02x%02x%02x' % (r, g, b)


class _TooltipManager:

    # This needs to be shared by all instances because there's only one
    # mouse pointer.
    tipwindow = None

    def __init__(self, widget):
        widget.bind('<Enter>', self.enter, add=True)
        widget.bind('<Leave>', self.leave, add=True)
        widget.bind('<Motion>', self.motion, add=True)
        self.widget = widget
        self.got_mouse = False
        self.text = None

    @classmethod
    def destroy_tipwindow(cls, junk_event=None):
        if cls.tipwindow is not None:
            cls.tipwindow.destroy()
            cls.tipwindow = None

    def enter(self, event):
        # For some reason, toplevels get also notified of their
        # childrens' events.
        if event.widget is self.widget:
            self.destroy_tipwindow()
            self.got_mouse = True
            self.widget.after(1000, self.show)

    def leave(self, event):
        if event.widget is self.widget:
            self.destroy_tipwindow()
            self.got_mouse = False

    def motion(self, event):
        self.mousex = event.x_root
        self.mousey = event.y_root

    def show(self):
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


def set_tooltip(widget, text):
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
    if text is None:
        if hasattr(widget, '_tooltip_manager'):
            widget._tooltip_manager.text = None
    else:
        if not hasattr(widget, '_tooltip_manager'):
            widget._tooltip_manager = _TooltipManager(widget)
        widget._tooltip_manager.text = text


def bind_with_data(widget, sequence, callback, add=False):
    """
    Like ``widget.bind(sequence, callback)``, but supports the ``data``
    argument of ``event_generate()``.

    Here's an example::

        from porcupine import utils

        def on_wutwut(event):
            print(event.data)

        utils.bind_with_data(some_widget, '<<Thingy>>', on_wutwut, add=True)

        # this prints 'wut wut'
        some_widget.event_generate('<<Thingy>>', data='wut wut')

    Note that everything is a string in Tcl, so tkinter ``str()``'s the data.

    The event objects have all the attributes that tkinter events
    usually have, and these additional attributes:

        ``data``
            See the above example.

        ``data_int`` and ``data_float``
            These are set to ``int(event.data)`` and ``float(event.data)``,
            or None if ``data`` is not a valid integer or float.

        ``data_widget``
            If a widget was passed as ``data`` to ``event_generate()``,
            this is that widget. Otherwise this is None.
        ``data_tuple(converter1, converter2, ...)``
            If a string from :func:`.create_tcl_list` is passed to
            ``event_generate()``, this splits the list back to the strings
            passed to :func:`.create_tcl_list` and optionally converts them to
            other types like ``converter(string_value)``. For example,
            ``event.data_tuple(int, int, str, float)`` returns a 4-tuple with
            types ``(int, int, str, float)``, throwing an error if some of the
            elements can't be converted or the iterable passed to
            :func:`.create_tcl_list` didn't contain exactly 4 elements.
    """
    # tkinter creates event objects normally and appends them to the
    # deque, then run_callback() adds data_blablabla attributes to the
    # event objects and runs callback(event)
    event_objects = collections.deque()
    widget.bind(sequence, event_objects.append, add=add)

    def run_the_callback(data_string):
        event = event_objects.popleft()
        event.data = data_string

        # TODO: test this
        try:
            split_result = event.widget.tk.splitlist(data_string)
        except tkinter.TclError:
            event.data_tuple = None
        else:
            def data_tuple(*converters):
                if len(split_result) != len(converters):
                    raise ValueError(
                        "the event data has %d elements, but %d converters "
                        "were given" % (len(split_result), len(converters)))
                return tuple(
                    converter(string)
                    for converter, string in zip(converters, split_result))

            event.data_tuple = data_tuple

        try:
            event.data_int = int(data_string)
        except ValueError:
            event.data_int = None

        try:
            event.data_float = float(data_string)
        except ValueError:
            event.data_float = None

        try:
            event.data_widget = widget.nametowidget(data_string)
        # nametowidget raises KeyError when the widget is unknown, but
        # that feels like an implementation detail
        except Exception:
            event.data_widget = None

        return callback(event)      # may return 'break'

    # tkinter's bind() ignores the add argument when the callback is a
    # string :(
    funcname = widget.register(run_the_callback)
    widget.tk.eval('bind %s %s {+ if {"[%s %%d]" == "break"} break }'
                   % (widget, sequence, funcname))
    return funcname


# TODO: document this
# TODO: test this
def create_tcl_list(iterable):
    widget = porcupine.get_main_window()      # any widget would do

    # in tcl, 'join [list x y z]' returns 'x y z', but 'join [list x]'
    # converts x to a string... let's do that, tkinter converts python tuples
    # to tcl lists
    python_tuple = tuple(map(str, iterable))
    result = widget.tk.call('join', (python_tuple,))
    assert isinstance(result, str)
    assert widget.tk.splitlist(result) == python_tuple
    return result


@contextlib.contextmanager
def temporary_bind(widget, sequence, func):
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
def bind_tab_key(widget, on_tab, **bind_kwargs):
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
    def callback(shifted, event):
        return on_tab(event, shifted)

    if widget.tk.call('tk', 'windowingsystem') == 'x11':
        # even though the event keysym says Left, holding down the right
        # shift and pressing tab also works :D
        shift_tab = '<ISO_Left_Tab>'
    else:
        shift_tab = '<Shift-Tab>'

    widget.bind('<Tab>', functools.partial(callback, False), **bind_kwargs)
    widget.bind(shift_tab, functools.partial(callback, True), **bind_kwargs)


def bind_mouse_wheel(widget, callback, *, prefixes='', **bind_kwargs):
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
        def real_callback(event):
            callback('up' if event.num == 4 else 'down')

        widget.bind('<{}Button-4>'.format(prefixes),
                    real_callback, **bind_kwargs)
        widget.bind('<{}Button-5>'.format(prefixes),
                    real_callback, **bind_kwargs)

    else:
        # TODO: test this on OSX
        def real_callback(event):
            callback('up' if event.delta > 0 else 'down')

        widget.bind('<{}MouseWheel>'.format(prefixes),
                    real_callback, **bind_kwargs)


def copy_bindings(widget1, widget2):
    """Add all bindings of *widget1* to *widget2*.

    You may need to call ``copy_bindings(porcupine.get_main_window(), widget)``
    on widgets that can be focused by clicking them, like ``Text`` and
    ``Entry`` widgets. Porcupine's keyboard bindings return ``'break'``
    and are bound to the main window, and thus work by default, but in
    some cases returning ``'break'`` doesn't do anything when the focus
    is in another widget inside the main window.
    """
    # tkinter's bind() can do quite a few different things depending
    # on how it's invoked
    for sequence in widget1.bind():
        tcl_command = widget1.bind(sequence)

        # add=True doesn't work if the command is a string :(
        widget2.tk.call('bind', widget2, sequence, '+' + tcl_command)


# see docs/utils.rst for explanation and docs
try:
    Spinbox = ttk.Spinbox
except AttributeError:
    try:
        Spinbox = ttk.SpinBox
    except AttributeError:
        # this is based on the code of ttk.Combobox, if tkinter changes so
        # that this breaks then ttk.Spinbox will be probably added as well
        class Spinbox(ttk.Entry):

            def __init__(self, master=None, *, from_=None, **kwargs):
                if from_ is not None:
                    kwargs['from'] = from_  # this actually works
                super().__init__(master, 'ttk::spinbox', **kwargs)

            def configure(self, *args, **kwargs):
                if 'from_' in kwargs:
                    kwargs['from'] = kwargs.pop('from_')
                return super().configure(*args, **kwargs)

            config = configure


def errordialog(title, message, monospace_text=None):
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


def run_in_thread(blocking_function, done_callback):
    """Run ``blocking_function()`` in another thread.

    If the *blocking_function* raises an error,
    ``done_callback(False, traceback)`` will be called where *traceback*
    is the error message as a string. If no errors are raised,
    ``done_callback(True, result)`` will be called where *result* is the
    return value from *blocking_function*. The *done_callback* is always
    called from Tk's main loop, so it can do things with Tkinter widgets
    unlike *blocking_function*.
    """
    root = porcupine.get_main_window()
    result = []     # [success, result]

    def thread_target():
        # the logging module uses locks so calling it from another
        # thread should be safe
        try:
            value = blocking_function()
            result[:] = [True, value]
        except Exception as e:
            result[:] = [False, traceback.format_exc()]

    def check():
        if thread.is_alive():
            # let's come back and check again later
            root.after(100, check)
        else:
            done_callback(*result)

    thread = threading.Thread(target=thread_target)
    thread.start()
    root.after_idle(check)


@contextlib.contextmanager
def backup_open(path, *args, **kwargs):
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
    if os.path.exists(path):
        # there's something to back up
        name, ext = os.path.splitext(path)
        while os.path.exists(name + ext):
            name += '-backup'
        backuppath = name + ext

        log.info("backing up '%s' to '%s'", path, backuppath)
        shutil.copy(path, backuppath)

        try:
            yield open(path, *args, **kwargs)
        except Exception as e:
            log.info("restoring '%s' from the backup", path)
            shutil.move(backuppath, path)
            raise e
        else:
            log.info("deleting '%s'" % backuppath)
            os.remove(backuppath)

    else:
        yield open(path, *args, **kwargs)


def get_keyboard_shortcut(binding):
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
