import pathlib
import platform

import appdirs  # type: ignore[import]

if platform.system() in {'Windows', 'Darwin'}:
    # these platforms like path names like "Program Files" or
    # "Application Support"
    _appname = 'Porcupine'
    _author = 'Akuli'
else:
    _appname = 'porcupine'
    _author = 'akuli'

cachedir: pathlib.Path = pathlib.Path(appdirs.user_cache_dir(_appname, _author))
configdir: pathlib.Path = pathlib.Path(appdirs.user_config_dir(_appname, _author))
logdir: pathlib.Path = pathlib.Path(appdirs.user_log_dir(_appname, _author))


def makedirs() -> None:
    all_paths = [cachedir, configdir, configdir / 'plugins', logdir]
    for path in all_paths:
        path.mkdir(parents=True, exist_ok=True)
