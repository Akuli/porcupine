"""Handy utility functions and classes."""

import atexit
import base64
import contextlib
import functools
import logging
import os
import pkgutil
import platform
import shutil
import sys
import threading
import tkinter as tk
import traceback

import porcupine

log = logging.getLogger(__name__)


class CallbackHook:
    """Simple object that runs callbacks.

    >>> hook = CallbackHook('whatever')
    >>> @hook.connect
    ... def user_callback(value):
    ...     print("user_callback called with", value)
    ...
    >>> hook.run(123)       # usually porcupine does this
    user_callback called with 123

    You can hook multiple callbacks too:

    >>> @hook.connect
    ... def another_callback(value):
    ...     print("another_callback called with", value)
    ...
    >>> hook.run(456)
    user_callback called with 456
    another_callback called with 456

    Errors in the connected functions will be logged to
    ``logging.getLogger(logname)``. The *unhandled_errors* argument
    should be an iterable of exceptions that won't be handled.
    """

    def __init__(self, logname, *, unhandled_errors=()):
        self._log = logging.getLogger(logname)
        self._unhandled = tuple(unhandled_errors)  # isinstance() likes tuples
        self.callbacks = []

    def connect(self, callback):
        """Schedule a function to be called when the hook is ran.

        This appends *callback* to :attr:`~callbacks`. The *callback* is
        also returned, so this can be used as a decorator.
        """
        self.callbacks.append(callback)
        return callback

    def disconnect(self, callback):
        """Remove *callback* from :attr:`~callbacks`."""
        self.callbacks.remove(callback)

    def _handle_error(self, callback, error):
        if isinstance(error, self._unhandled):
            raise error
        self._log.exception("%s doesn't work", nice_repr(callback))

    def run(self, *args):
        """Run ``callback(*args)`` for each connected callback."""
        for callback in self.callbacks:
            try:
                callback(*args)
            except Exception as e:
                self._handle_error(callback, e)


# pythonw.exe sets sys.stdout to None because there's no console window,
# print still works because it checks if sys.stdout is None
running_pythonw = (sys.stdout is None)

# this is a hack :(
python = sys.executable
if running_pythonw and sys.executable.lower().endswith(r'\pythonw.exe'):
    # get rid of the 'w'
    _possible_python = sys.executable[:-5] + sys.executable[-4:]
    if os.path.isfile(_possible_python):
        python = _possible_python

# get rid of symlinks and make it absolute
python = os.path.realpath(python)


# TODO: document quote()
if platform.system() == 'Windows':
    # this is mostly copy/pasted from subprocess.list2cmdline
    def quote(string):
        """Like shlex.quote, but for Windows.

        >>> quote('test')
        'test'
        >>> quote('test thing')
        '"test thing"'
        """
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
    from shlex import quote    # noqa


# TODO: add this to docs/utils.rst
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


# this is currently not used anywhere, but i spent a while figuring out
# how to do this and it might be useful in the future
# TODO: document this in docs/utils.rst
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
    inside the ``with`` block.
    """
    not_bound_commands = widget.bind(sequence)
    tcl_command = widget.bind(sequence, func, add=True)
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

        utils.bind_tab(some_widget, on_tab, add=True)

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
    for keysym in widget1.bind():
        tcl_command = widget1.bind(keysym)
        widget2.bind(keysym, tcl_command)


def bind_mouse_wheel(widget, callback, *, prefixes='', **bind_kwargs):
    """Bind mouse wheel events to callback.

    The callback will be called like ``callback(direction)`` where
    *direction* is ``'up'`` or ``'down'``. The *prefixes* argument can
    be used to change the binding string. For example,
    ``prefixes='Control-'`` means that callback will be ran when the
    user holds down Control and rolls the wheel.
    """
    # i needed to cheat and use stackoverflow, the man pages don't say
    # what OSX does with MouseWheel events and i don't have an
    # up-to-date OSX :( the non-x11 code should work on windows and osx
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


# FIXME: is lru_cache() guaranteed to hold references? tkinter's images
# use __del__ and it's important to hold a reference to them as long as
# they're used somewhere
@functools.lru_cache()
def get_image(filename):
    """Create a ``tkinter.PhotoImage`` from a file in ``porcupine/images``.

    This function is cached and the cache holds references to all
    returned images, so there's no need to worry about calling this
    function too many times or keeping references to the returned
    images.
    """
    # only gif images should be added to porcupine/images, other image
    # formats don't work with old Tk versions
    data = pkgutil.get_data('porcupine', 'images/' + filename)
    return tk.PhotoImage(format='gif', data=base64.b64encode(data))


# cpython exits like this:
#   1) atexit callbacks run
#   2) module globals are set to None (wtf lol)
#   3) all objects are destroyed and __del__ methods run
#
# the problem here is that tkinter.Image.__del__ does "except TclError",
# but tkinter.TclError is already None, it's not a big deal but this
# silences those errors
atexit.register(get_image.cache_clear)


def errordialog(title, message, monospace_text=None):
    """This is a lot like ``tkinter.messagebox.showerror``.

    Don't rely on this, I'll probably move this to
    :mod:`porcupine.dialogs` later.

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
        window = tk.Tk()
    else:
        window = tk.Toplevel()
        window.transient(root)

    label = tk.Label(window, text=message, height=5)

    if monospace_text is None:
        label.pack(fill='both', expand=True)
        geometry = '250x150'
    else:
        label.pack(anchor='center')
        text = tk.Text(window, width=1, height=1)
        text.pack(fill='both', expand=True)
        text.insert('1.0', monospace_text)
        text['state'] = 'disabled'
        geometry = '400x300'

    button = tk.Button(window, text="OK", width=6, command=window.destroy)
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


class Checkbox(tk.Checkbutton):
    """Like ``tkinter.Checkbutton``, but works with my dark GTK+ theme.

    Tkinter's Checkbutton displays a white checkmark on a white
    background on my dark GTK+ theme (BlackMATE on Mate 1.8). This class
    fixes that.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self['selectcolor'] == self['foreground'] == '#ffffff':
            self['selectcolor'] = self['background']


def nice_repr(obj):
    """Don't rely on this, this may be removed later.

    Return a nice string representation of an object.

    >>> import time
    >>> nice_repr(time.strftime)
    'time.strftime'
    >>> nice_repr(object())     # doctest: +ELLIPSIS
    '<object object at 0x...>'
    """
    try:
        return obj.__module__ + '.' + obj.__qualname__
    except AttributeError:
        return repr(obj)


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


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
