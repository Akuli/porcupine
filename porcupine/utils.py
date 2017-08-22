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
import subprocess
import sys
import threading
import tkinter as tk
import traceback

import porcupine
from porcupine import dirs

log = logging.getLogger(__name__)


# pythonw.exe sets sys.stdout to None because there's no console window,
# print still works because it checks if sys.stdout is None
running_pythonw = (sys.stdout is None)

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


# TODO: document quote()
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
    from shlex import quote    # noqa


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


def bind_data_event(widget, sequence, func, *, add=False):
    """Bind a virtual event that supports passing data to a callback function.

    This is a lot like ``widget.bind(sequence, func, add=add)``, except
    that the function's argument will be the value of a *data* argument
    passed to ``event_generate()`` instead of a ``tkinter.Event``
    object. This function is needed because ``Event`` objects don't have
    a *data* attribute for some reason, even on Python 3.7.

    Example::

        import tkinter as tk
        from porcupine import utils

        root = tk.Tk()
        root.update()   # the widget must be visible for virtual events to work
        utils.bind_data_event(root, '<<Hello>>', print, add=True)
        root.event_generate('<<Hello>>', data="hello")   # runs print("hello")

    Note that the data is always converted to a string. The *add*
    argument is False by default for consistency with tkinter's
    ``bind()`` method.

    .. seealso::
        The *data* option is documented as ``-data string`` in
        :man:`event(3tk)`.
    """
    # %d means data here, not digit
    # i could escape this with %%d or {{ }} instead of the .replace, but
    # it would be overkill imo
    bind_script = '''
    # make sure that returning 'break' works, tkinter does this too
    if {"[FUNCNAME %d]" == "break"} {
        break
    }
    '''.replace('FUNCNAME', widget.register(func))

    # add=True doesn't work if the second argument to bind() is a string -_-
    # bind(3tk) says: "If script is prefixed with a "+", then it is
    # appended to any existing binding for sequence"
    if add:
        bind_script = '+' + bind_script
    widget.tk.call('bind', str(widget), sequence, bind_script)


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


# tkinter images destroy themselves on __del__. here's how cpython exits:
#
#   1) atexit callbacks run
#   2) module globals are set to None (lol)
#   3) all objects are destroyed and __del__ methods run
#
# tkinter.Image.__del__ destroys the image, and that uses
# "except TclError". this causes means two things:
#
#   - it's necessary to hold references to the images to avoid calling
#     __del__ while they're being used somewhere
#   - the images must be destroyed before step 2 above
_images = []
atexit.register(_images.clear)


# TODO: document this behavior
def _init_images():
    for filename in os.listdir(os.path.join(dirs.installdir, 'images')):
        no_ext, ext = os.path.splitext(filename)
        # only gif images should be added to porcupine/images, other
        # image formats don't work with old Tk versions
        if ext == '.gif':
            image = tk.PhotoImage(
                name=('img_' + no_ext),
                file=os.path.join(dirs.installdir, 'images', filename))
            _images.append(image)


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
