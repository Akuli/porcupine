"""An API for accessing images."""

import atexit
import os
import tkinter

# __path__[0] is the directory where this __init__.py is
images_dir = os.path.abspath(__path__[0])


# tkinter images destroy themselves on __del__. here's how cpython exits:
#
#   1) atexit callbacks run
#   2) module globals are set to None (lol)
#   3) all objects are destroyed and __del__ methods run
#
# tkinter.Image.__del__ destroys the image, and that uses
# "except TclError". this causes means two things:
#
#   - it's necessary to hold references to the images to avoid calling
#     __del__ while they're being used somewhere
#   - the images must be destroyed before step 2 above
#
# tldr: the cache is not just a performance or memory optimization
_image_cache = {}        # {name: PhotoImage}
atexit.register(_image_cache.clear)


def get(name):
    """Load a ``tkinter.PhotoImage`` from an image file that comes with Porcup\
ine.

    The name should be the name of a file in :source:`porcupine/images`
    without the extension, e.g. ``'triangle'``. If this function is
    called multiple times with the same name, the same image object is
    returned every time.
    """
    if name in _image_cache:
        return _image_cache[name]

    files = [filename for filename in os.listdir(images_dir)
             if filename.startswith(name + '.')]
    if not files:
        raise FileNotFoundError("no image file named %r" % name)
    assert len(files) == 1, "there are multiple %r files" % name

    image = tkinter.PhotoImage(file=os.path.join(images_dir, files[0]))
    _image_cache[name] = image
    return image
