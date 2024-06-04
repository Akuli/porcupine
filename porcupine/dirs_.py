r"""This module defines folders where Porcupine stores files.

Folders on most Windows systems:
    config_dir = C:\Users\<username>\AppData\Local\Akuli\Porcupine
    cache_dir  = C:\Users\<username>\AppData\Local\Akuli\Porcupine\Cache
    log_dir    = C:\Users\<username>\AppData\Local\Akuli\Porcupine\Logs

Folders on most MacOS systems:
    config_dir = /Users/<username>/Library/Application Support/Porcupine
    cache_dir  = /Users/<username>/Library/Caches/Porcupine
    log_dir    = /Users/<username>/Library/Logs/Porcupine

Folders on most Linux systems:
    config_dir = /home/<username>/.config/porcupine
    cache_dir  = /home/<username>/.cache/porcupine
    log_dir    = /home/<username>/.cache/porcupine/log

Libraries like `platformdirs` exist, but a custom thing makes it easier to
explain to users where Porcupine is storing its files. Using many small
dependencies is also bad from a security point of view.
"""

from pathlib import Path
import os
import sys


if sys.platform == "win32":
    # %LOCALAPPDATA% seems to be a thing on all reasonably new Windows systems.
    _localappdata = os.getenv("LOCALAPPDATA")
    if not _localappdata:
        raise RuntimeError("%LOCALAPPDATA% is not set")

    # Porcupine uses local appdata for historical reasons.
    # I'm not sure whether it is better or worse than the roaming appdata.
    # Please create an issue if you think Porcupine should use the roaming appdata instead.
    config_dir = Path(_localappdata) / "Akuli" / "Porcupine"
    cache_dir = config_dir / "Cache"
    log_dir = config_dir / "Logs"

elif sys.platform == "darwin":
    config_dir = Path("~/Library/Application Support/Porcupine").expanduser()
    cache_dir = Path("~/Library/Caches/Porcupine").expanduser()
    log_dir = Path("~/Library/Logs/Porcupine").expanduser()

else:
    # This code is for linux, and for Tuomas running Porcupine on NetBSD.
    #
    # See https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
    # for env vars and the fallbacks to be used when they are "either not set or empty".
    # In reality, nobody uses these env vars, so the fallbacks are important.
    config_dir = Path(os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")) / "porcupine"
    cache_dir = Path(os.getenv("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")) / "porcupine"
    log_dir = cache_dir / "log"
