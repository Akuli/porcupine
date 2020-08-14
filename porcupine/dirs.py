import pathlib
import platform

import appdirs      # type: ignore

from porcupine import __author__ as _author


if platform.system() in {'Windows', 'Darwin'}:
    # these platforms like path names like "Program Files" or
    # "Application Support"
    _appname = 'Porcupine'
else:
    _appname = 'porcupine'
    _author = _author.lower()

cachedir: pathlib.Path = pathlib.Path(
    appdirs.user_cache_dir(_appname, _author))
configdir: pathlib.Path = pathlib.Path(
    appdirs.user_config_dir(_appname, _author))

# this hack shouldn't be a problem because porcupine isn't distributed
# with tools like pyinstaller, and it doesn't need to be because people
# using porcupine have python installed anyway
installdir = pathlib.Path(__file__).absolute().parent


def makedirs() -> None:
    all_paths = [cachedir, configdir, configdir / 'plugins']
    for path in all_paths:
        path.mkdir(parents=True, exist_ok=True)
