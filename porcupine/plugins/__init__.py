"""
If you want to write more plugins, that's great! Have a look at the documentation:

    https://akuli.github.io/porcupine/
"""
from __future__ import annotations

import os

from porcupine import dirs

# simple hack to allow user-wide plugins
__path__.insert(0, os.path.join(dirs.user_config_dir, "plugins"))
