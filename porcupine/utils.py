"""Handy utility functions."""

import base64
import functools
import pkgutil
import tkinter as tk


@functools.lru_cache()
def get_image(filename):
    """Create a tkinter PhotoImage from a file in porcupine/images.

    This function is cached and the cache holds references to all
    returned images, so there's no need to worry about calling this
    function too many times or keeping reference to the returned images.

    Only gif images should be added to porcupine/images. Other image
    formats don't work with old Tk versions.
    """
    data = pkgutil.get_data('porcupine', 'images/' + filename)
    return tk.PhotoImage(format='gif', data=base64.b64encode(data))


@functools.lru_cache()
def windowingsystem():
    """Run "tk windowingsystem" in the Tcl interpreter.

    A tkinter root window must exist.
    """
    # tkinter's default root window is not accessible as a part of the
    # public API
    try:
        widget = tk._default_root
        gonna_destroy = False
    except AttributeError:
        widget = tk.Label()
        gonna_destroy = True

    result = widget.tk.call('tk', 'windowingsystem')
    if gonna_destroy:
        widget.destroy()
    return result
