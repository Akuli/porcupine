"""Load image files from :source:`porcupine/images`."""
from __future__ import annotations

import atexit
import tkinter
from pathlib import Path
from tkinter.ttk import Style

from porcupine import utils

# __path__[0] is the directory where this __init__.py is
__path__: list[str]
images_dir = Path(__path__[0]).absolute()


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
_image_cache: dict[str, tkinter.PhotoImage] = {}
atexit.register(_image_cache.clear)

# these icons can be found in both dark and light versions, so you can see them with any ttk theme
_images_that_can_be_dark_or_light = {"closebutton"}


def _generate_themed_name(name: str):
    # I don't like using ttk.Style, but it'd be complicated without it
    is_light = utils.is_bright(Style().lookup("TLabel.label", "background"))
    return f"{name}_{'dark' if is_light else 'light'}"


def _get_image_file(name: str):
    paths = [path for path in images_dir.iterdir() if path.stem == name]

    if not paths:
        raise FileNotFoundError(f"no image file named {name!r}")
    assert len(paths) == 1, f"there are multiple {name!r} files"

    return paths[0]


def _config_images(*junk):
    for name in _images_that_can_be_dark_or_light:
        if name in _image_cache:
            _image_cache[name].config(file=_get_image_file(_generate_themed_name(name)))


def get(name: str) -> tkinter.PhotoImage:
    """Load a ``tkinter.PhotoImage`` from an image file that comes with Porcupine.

    The name should be the name of a file in :source:`porcupine/images`
    without the extension, e.g. ``'triangle'``. If this function is
    called multiple times with the same name, the same image object is
    returned every time.
    """
    if name in _image_cache:
        return _image_cache[name]

    real_name = name

    if name in _images_that_can_be_dark_or_light:
        real_name = _generate_themed_name(name)

    image = tkinter.PhotoImage(file=_get_image_file(real_name))
    _image_cache[name] = image
    return image
