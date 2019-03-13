import atexit
import functools
import os

import teek as tk


# __path__[0] is the directory where this __init__.py is
images_dir = os.path.abspath(__path__[0])


@functools.lru_cache()
def get(name):
    """Load a :class:`pythotk.Image`` from an image file that comes with Porcu\
pine.

    The name should be the name of a file in :source:`porcupine/images`
    without the extension, e.g. ``'triangle'``. If this function is
    called multiple times with the same name, the same image object is
    returned every time.
    """
    files = [filename for filename in os.listdir(images_dir)
             if filename.startswith(name + '.')]
    if not files:
        raise FileNotFoundError("no image file named %r" % name)
    assert len(files) == 1, "there are multiple %r files" % name

    return tk.Image(file=os.path.join(images_dir, files[0]))
