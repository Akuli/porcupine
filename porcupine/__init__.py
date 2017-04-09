# this docstring doesn't contain a one-line summary because editor.py
# uses it as a welcome message
"""
Porcupine is a simple, beginner-friendly editor for writing Python code.
If you ever used anything like Notepad, Microsoft Word or LibreOffice
Writer before, you will feel right at home.

You can create a new file by pressing Ctrl+N or open an existing file by
pressing Ctrl+O. The file name will be displayed in red if the file has
been changed and you can save the file with Ctrl+S.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

import os
import platform
import traceback

from porcupine import utils

try:
    import appdirs
except ImportError:
    try:
        # some versions of pip seem to come with a copy of appdirs, but
        # it's an implementation detail so we need to make sure it's
        # actually compatible
        from pip._vendor import appdirs
        appdirs.AppDirs.user_cache_dir
        appdirs.AppDirs.user_config_dir
    except (ImportError, AttributeError) as e:
        # i know i know, running GUI dialogs on import sucks
        traceback.print_exc()
        utils.errordialog(
            "Importing appdirs failed",
            "Looks like appdirs is not installed. " +
            "You can install it like this:",
            ">>> import pip\n" +
            ">>> pip.main(['install', '--user', 'appdirs'])")
        raise ImportError("appdirs not found") from e


class _PorcupineDirs(appdirs.AppDirs):

    # handy aliases because porcupine doesn't use the system-wide dirs
    # and there's no risk of confusing them with these
    cachedir = appdirs.AppDirs.user_cache_dir
    configdir = appdirs.AppDirs.user_config_dir

    # and some other stuff
    @property
    def installdir(self):
        # this hack shouldn't be a problem because porcupine isn't
        # distributed with tools like pyinstaller, and it doesn't need
        # to be because people using porcupine have python installed
        # anyway
        return os.path.dirname(os.path.abspath(__file__))

    @property
    def userplugindir(self):
        return os.path.join(self.configdir, 'plugins')

    def makedirs(self):
        all_paths = [self.cachedir, self.configdir, self.userplugindir]
        for path in all_paths:
            os.makedirs(path, exist_ok=True)


if platform.system() in {'Windows', 'Darwin'}:
    dirs = _PorcupineDirs('Porcupine', 'Akuli')
else:
    dirs = _PorcupineDirs('porcupine', 'Akuli')
