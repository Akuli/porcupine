"""Handy utility functions and classes."""

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

    Callback hooks have a ``callbacks`` attribute that contains a list
    of hooked functions. It's useful for things like checking if a
    callback has been connected.

    >>> hook.callbacks == [user_callback, another_callback]
    True

    Errors in the connected functions will be logged to
    ``logging.getLogger(logname)``. The *unhandled_errors* argument
    should be an iterable of exceptions that won't be handled.
    """

    def __init__(self, logname, *, unhandled_errors=()):
        self._log = logging.getLogger(logname)
        self._unhandled = tuple(unhandled_errors)  # isinstance() likes tuples
        self._blocklevel = 0
        self.callbacks = []

    def connect(self, function):
        """Schedule a function to be called when the hook is ran.

        The function is returned too, so this can be used as a
        decorator.
        """
        self.callbacks.append(function)
        return function

    def disconnect(self, function):
        """Undo a :meth:`connect` call."""
        self.callbacks.remove(function)

    @contextlib.contextmanager
    def blocked(self):
        """Prevent the callbacks from running temporarily.

        Use this as a context manager, like this::

            with some_hook.blocked():
                # do something that would normally run the callbacks
        """
        self._blocklevel += 1
        try:
            yield
        finally:
            self._blocklevel -= 1

    def is_blocked(self):
        """Return True if :meth:`~blocked` is running somewhere."""
        assert self._blocklevel >= 0
        return self._blocklevel > 0

    def _handle_error(self, callback, error):
        if isinstance(error, self._unhandled):
            raise error
        self._log.exception("%s doesn't work", nice_repr(callback))

    def run(self, *args):
        """Run ``callback(*args)`` for each connected callback.

        This does nothing if :meth:`~blocked` is currently running.
        """
        if not self.is_blocked():
            for callback in self.callbacks:
                try:
                    callback(*args)
                except Exception as e:
                    self._handle_error(callback, e)


class ContextManagerHook(CallbackHook):
    """A :class:`.CallbackHook` subclass for "set up and tear down" callbacks.

    The connected callbacks should usually do something, yield and then
    undo everything they did, just like :func:`contextlib.contextmanager`
    functions.

    >>> hook = ContextManagerHook('whatever')
    >>> @hook.connect
    ... def hooked_callback():
    ...     print("setting up")
    ...     yield
    ...     print("tearing down")
    ...
    >>> with hook.run():
    ...     print("now things are set up")
    ...
    setting up
    now things are set up
    tearing down
    >>>
    """

    @contextlib.contextmanager
    def run(self, *args):
        """Run ``callback(*args)`` for each connected callback.

        This does nothing if :meth:`~blocked` is currently running.
        """
        if self.is_blocked():
            return

        generators = []   # [(callback, generator), ...]
        for callback in self.callbacks:
            try:
                generator = callback(*args)
                if not hasattr(type(generator), '__next__'):
                    # it has no yields at all
                    raise RuntimeError("the function didn't yield")

                try:
                    next(generator)
                except StopIteration:
                    # it has a yield but it didn't run, e.g. if False: yield
                    raise RuntimeError("the function didn't yield")

                generators.append((callback, generator))

            except Exception as e:
                self._handle_error(callback, e)

        yield

        for callback, generator in generators:
            try:
                next(generator)     # should raise StopIteration
                raise RuntimeError("the function yieleded twice")
            except StopIteration:
                pass
            except Exception as e:
                self._handle_error(callback, e)


# TODO: document these
running_pythonw = (
    platform.system() == 'Windows' and
    os.path.basename(sys.executable).lower() == 'pythonw.exe')

if running_pythonw:
    # get rid of 'w'
    python = sys.executable[:-5] + sys.executable[-4:]
else:
    python = sys.executable


@functools.lru_cache()
def get_image(filename):
    """Create a tkinter PhotoImage from a file in porcupine/images.

    This function is cached and the cache holds references to all
    returned images, so there's no need to worry about calling this
    function too many times or keeping reference to the returned images.

    Only gif images should be added to porcupine/images. Other image
    formats don't work with old Tk versions.
    """
    data = pkgutil.get_data('porcupine', 'images/' + filename)
    return tk.PhotoImage(format='gif', data=base64.b64encode(data))


def get_root():
    """Return tkinter's current root window."""
    # tkinter's default root window is not accessible as a part of the
    # public API, but tkinter uses _default_root everywhere so I don't
    # think it's going away
    return tk._default_root


def get_window(widget):
    """Return the tk.Tk or tk.Toplevel widget that a widget is in."""
    while not isinstance(widget, (tk.Tk, tk.Toplevel)):
        widget = widget.master
    return widget


def errordialog(title, message, monospace_text=None):
    """A lot like ``tkinter.messagebox.showerror``.

    This function can be called with or without creating a root window
    first. If *monospace_text* is not None, it will be displayed below
    the message in a ``tkinter.Text`` widget.
    """
    root = get_root()
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


def copy_bindings(widget1, widget2):
    """Add all bindings of *widget1* to *widget2*.

    You should call ``copy_bindings(editor, focusable_widget)`` on all
    widgets that can be focused by e.g. clocking them, like ``Text`` and
    ``Entry`` widgets. This way porcupine's keyboard bindings will work
    with all widgets.
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
    if get_root().tk.call('tk', 'windowingsystem') == 'x11':
        def real_callback(event):
            callback('up' if event.num == 4 else 'down')

        widget.bind('<{}Button-4>'.format(prefixes),
                    real_callback, **bind_kwargs)
        widget.bind('<{}Button-5>'.format(prefixes),
                    real_callback, **bind_kwargs)

    else:
        def real_callback(event):
            callback('up' if event.delta > 0 else 'down')

        widget.bind('<{}MouseWheel>'.format(prefixes),
                    real_callback, **bind_kwargs)


def nice_repr(obj):
    """Return a nice string representation of an object.

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


def run_in_thread(blocking_function, done_callback):
    """Run ``done_callback(True, blocking_function())`` in the background.

    This function runs ``blocking_function()`` with no arguments in a
    thread. If the *blocking_function* raises an error,
    ``done_callback(False, traceback)`` will be called where *traceback*
    is the error message as a string. If no errors are raised,
    ``done_callback(True, result)`` will be called where *result* is the
    return value from *blocking_function*.

    The *done_callback* will be always called from Tk's main loop, so it
    can do things with Tkinter widgets unlike *blocking_function*.
    """
    root = get_root()
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

    This automatically restores from a backup on failure.
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


class HandyText(tk.Text):
    """Like ``tkinter.Text``, but with some handy features.

    All arguments are passed to ``tkinter.Text``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursorpos = (1, 0)

        #: This :class:`~CallbackHook` will be ran when the user moves
        #: the cursor. It will be ran with the line and column numbers
        #: as arguments, where 1 is the first line and 0 is the first
        #: column.
        self.cursor_move_hook = CallbackHook(__name__)

        #: This :class:`~CallbackHook` will be ran with no arguments
        #: when the user changes the content of the widget in any way or
        #: methods like ``insert()`` or ``delete()`` are used. Use this
        #: instead of binding ``<<Modified>>``.
        self.modified_hook = CallbackHook(__name__)

        def cursor_move(event):
            self.after_idle(self.cursor_has_moved)

        for keysym in [
                '<Button-1>', '<Key>', '<<Undo>>', '<<Redo>>',
                '<<Cut>>', '<<Copy>>', '<<Paste>>', '<<Selection>>']:
            self.bind(keysym, cursor_move, add=True)

    def cursor_has_moved(self):
        """Call this when the cursor may have moved.

        This does nothing if the cursor hasn't actually moved, so you
        don't need to worry about calling this too often. You may need
        to use ``after_idle`` if you are calling this from an event
        handler::

            def the_bind_callback(event):
                ...
                handytext.after_idle(handytext.cursor_has_moved)
        """
        line, column = map(int, self.index('insert').split('.'))
        if (line, column) != self._cursorpos:
            self._cursorpos = (line, column)
            self.cursor_move_hook.run(line, column)

    # these methods may move the cursor
    # FIXME: add more movy method
    def insert(self, *args, **kwargs):
        super().insert(*args, **kwargs)
        self.cursor_has_moved()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.cursor_has_moved()

    def iter_chunks(self):
        """Iterate over the content as 100-line chunks.

        This does not break lines in the middle.
        """
        start = 1
        while True:
            end = start + 100
            if self.index('%d.0' % end) == self.index('end'):
                yield self.get('%d.0' % start, 'end - 1 char')
                break

            yield self.get('%d.0' % start, '%d.0' % end)
            start = end


class Checkbox(tk.Checkbutton):
    """Like ``tkinter.Checkbutton``, but works with my dark GTK+ theme.

    Tkinter's Checkbutton displays a white checkmark on a white
    background on my dark GTK+ theme (BlackMATE on Mate 1.8). This class
    fixes that.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print('aaa', self['highlightcolor'], self['foreground'])
        if self['selectcolor'] == self['foreground'] == '#ffffff':
            print('lulz', self['background'])
            self['selectcolor'] = self['background']


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
