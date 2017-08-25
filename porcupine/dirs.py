# TODO: move this to __init__.py? this was in a separate file because
# setup.py used to import porcupine but it doesn't do it anymore

import os
import platform

import appdirs

from porcupine import __author__ as _author


if platform.system() in {'Windows', 'Darwin'}:
    # these platforms like path names like "Program Files" or
    # "Application Support"
    _appname = 'Porcupine'
else:
    _appname = 'porcupine'
    _author = _author.lower()

cachedir = appdirs.user_cache_dir(_appname, _author)
configdir = appdirs.user_config_dir(_appname, _author)

# this hack shouldn't be a problem because porcupine isn't distributed
# with tools like pyinstaller, and it doesn't need to be because people
# using porcupine have python installed anyway
installdir = os.path.dirname(os.path.abspath(__file__))


def makedirs():
    all_paths = [cachedir, configdir, os.path.join(configdir, 'plugins')]
    for path in all_paths:
        os.makedirs(path, exist_ok=True)
