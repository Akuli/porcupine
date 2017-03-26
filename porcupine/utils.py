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


def bind_mouse_wheel(widget, callback, *, prefixes=''):
    """Bind mouse wheel events to callback.

    The callback will be called like callback(direction) where direction
    is 'up' or 'down'. The prefixes argument can be used to change the
    binding string. For example, prefixes='Control-' means that callback
    will be ran when the user holds down Control and rolls the wheel.
    """
    # i needed to cheat and use stackoverflow, the man pages don't say
    # what OSX does with MouseWheel events and i don't have an
    # up-to-date OSX :( the non-x11 code should work on windows and osx
    # http://stackoverflow.com/a/17457843
    if windowingsystem() == 'x11':
        def real_callback(event):
            callback('up' if event.num == 4 else 'down')

        widget.bind('<{}Button-4>'.format(prefixes), real_callback)
        widget.bind('<{}Button-5>'.format(prefixes), real_callback)

    else:
        def real_callback(event):
            callback('up' if event.delta > 0 else 'down')

        widget.bind('<{}MouseWheel>'.format(prefixes), real_callback)


class Checkbox(tk.Checkbutton):
    """Like tk.Checkbutton, but works with my dark GTK+ theme."""
    # tk.Checkbutton displays a white checkmark on a white background to
    # me, and changing the checkmark color also changes the text color

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print('aaa', self['highlightcolor'], self['foreground'])
        if self['selectcolor'] == self['foreground'] == '#ffffff':
            print('lulz', self['background'])
            self['selectcolor'] = self['background']
