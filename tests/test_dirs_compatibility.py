# TODO: delete this file once it passes CI successfully

import os
import sys

import platformdirs
from porcupine import dirs

if sys.platform in {"win32", "darwin"}:
    # these platforms like path names like "Program Files" or "Application Support"
    old_dirs = platformdirs.PlatformDirs("Porcupine", "Akuli")
else:
    # By default, platformdirs places logs to a weird place ~/.local/state/porcupine/log.
    # No other applications I have use ~/.local/state and it doesn't even exist on my system.
    # See https://github.com/platformdirs/platformdirs/issues/106
    class _PorcupinePlatformDirs(platformdirs.PlatformDirs):  # type: ignore
        @property
        def user_log_dir(self) -> str:
            return os.path.join(self.user_cache_dir, "log")

    # Also let's make the directory names lowercase
    old_dirs = _PorcupinePlatformDirs("porcupine", "akuli")


def test_dirs_compatibility():
    assert dirs.cache_dir == old_dirs.user_cache_dir
    assert dirs.config_dir == old_dirs.user_config_dir
    assert dirs.log_dir == old_dirs.user_log_dir
