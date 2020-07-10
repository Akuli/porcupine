"""Porcupine's plugins.

If you want to write more plugins, that's great! Have a look at the
official documentation:

    https://akuli.github.io/porcupine/
"""

import os
import typing

from porcupine import dirs

# simple hack to allow user-wide plugins
__path__: typing.List[str]
__path__.insert(0, os.path.join(dirs.configdir, 'plugins'))
