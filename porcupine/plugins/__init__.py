"""
If you want to write more plugins, that's great! Have a look at the documentation:

    https://akuli.github.io/porcupine/
"""

from typing import List

from porcupine import dirs

# simple hack to allow user-wide plugins
__path__: List[str]
__path__.insert(0, str(dirs.configdir / 'plugins'))
