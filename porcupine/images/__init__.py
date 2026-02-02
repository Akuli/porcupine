"""This code loads files from the `images` folder.

Example:

    from tkinter import ttk
    from porcupine import images

    label = ttk.Label(image=images.get("logo-200x200"))

Prefer the `logo-200x200` image over `logo` if you need to load an image when
Porcupine starts. Loading the full-size `logo` seems to take about 225
milliseconds on this system, while `logo-200x200` loads in about 5 milliseconds.

Some images are different for light and dark UI themes, but the returned
`tkinter.PhotoImage` objects update automatically to reflect the current theme.
For example, to use either `closebutton_dark.png` or `closebutton_light.png`,
you would simply do `images.get("closebutton")`.
"""

from __future__ import annotations

import atexit
import tkinter
from pathlib import Path
from tkinter.ttk import Style

from porcupine import utils

# __path__[0] is the directory where this __init__.py is
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

_images_that_can_be_dark_or_light = {"closebutton", "pause", "resume"}


def _get_image_file(name: str) -> Path:
    if name in _images_that_can_be_dark_or_light:
        # The "or" fallback is needed in some corner case that I don't fully
        # understand. This will later run again with the correct color.
        if utils.is_bright(Style().lookup("TLabel.label", "background") or "white"):
            name += "_dark"
        else:
            name += "_light"

    [path] = [
        path
        for path in images_dir.iterdir()
        if path.stem == name and path.suffix in (".gif", ".png")
    ]
    return path


def _update_dark_or_light_images(junk: object) -> None:
    for name in _images_that_can_be_dark_or_light:
        if name in _image_cache:
            _image_cache[name].config(file=_get_image_file(name))


def get(name: str) -> tkinter.PhotoImage:
    """Load a ``tkinter.PhotoImage`` from an image file that comes with Porcupine.

    The name should be the name of a file in :source:`porcupine/images`
    without the extension, e.g. ``'triangle'``. If this function is
    called multiple times with the same name, the same image object is
    returned every time.
    """
    if name in _image_cache:
        return _image_cache[name]

    image = tkinter.PhotoImage(file=_get_image_file(name))
    _image_cache[name] = image
    return image
