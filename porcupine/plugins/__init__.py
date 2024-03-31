"""This folder contains all plugins that come with Porcupine."""
from __future__ import annotations

from porcupine import dirs

# simple hack to allow user-wide plugins
__path__.insert(0, str(dirs.user_config_path / "plugins"))
