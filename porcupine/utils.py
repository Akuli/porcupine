"""Handy utility functions."""

import contextlib
import logging
import os
import platform
import shlex
import shutil
import string as string_module
import subprocess
import sys

import teek as tk

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


def invert_color(color: tk.Color):
    """
    Return a :class:`pythotk.Color` with opposite red, green and blue values.

    Example: ``invert_color(pythotk.Color('white')) == pythotk.color('black')``
    """
    return tk.Color(0xff - color.red, 0xff - color.green, 0xff - color.blue)


def bind_mouse_wheel(widget, callback, *, prefixes=''):
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
    if tk.windowingsystem() == 'x11':
        def real_callback(event):
            callback('up' if event.button == 4 else 'down')

        widget.bind('<{}Button-4>'.format(prefixes),
                    real_callback, event=True)
        widget.bind('<{}Button-5>'.format(prefixes),
                    real_callback, event=True)

    else:
        # TODO: test this on OSX
        def real_callback(event):
            callback('up' if event.delta > 0 else 'down')

        widget.bind('<{}MouseWheel>'.format(prefixes),
                    real_callback, event=True)


@tk.make_thread_safe
def errordialog(title, message, monospace_text=None):
    """This is a lot like ``tkinter.messagebox.showerror``.

    This function can be called with or without creating a root window
    first. If *monospace_text* is not None, it will be displayed below
    the message in a ``tkinter.Text`` widget.

    This function can be called from a thread.

    Example::

        try:
            do something
        except SomeError:
            utils.errordialog("Oh no", "Doing something failed!",
                              traceback.format_exc())
    """
    porcu_main_window = porcupine.get_main_window()
    window = tk.Window()
    window.transient = porcu_main_window

    label = tk.Label(window, message)

    if monospace_text is None:
        label.pack(fill='both', expand=True)
        size = (250, 150)
    else:
        label.pack(anchor='center')
        # there's no ttk.Text 0_o this looks very different from
        # everything else and it sucks :(
        text = tk.Text(window, width=1, height=1)
        text.pack(fill='both', expand=True)
        text.insert(text.start, monospace_text)
        text.config['state'] = 'disabled'
        size = (400, 300)

    button = tk.Button(window, text="OK", command=window.destroy)
    button.pack(pady=10)

    window.title = title
    window.geometry(*size)
    window.wait_window()


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
        # FIXME: does this close the file?
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
