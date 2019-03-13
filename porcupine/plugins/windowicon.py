import teek as tk

from porcupine import get_main_window, images


def setup():
    window = get_main_window()
    window.title = "Porcupine"    # not related to the icon, but it's ok imo

    # TODO: add 'wm iconphoto' to pythotk
    # fun fact: tkinter has it, but it's broken :D so this file contained a
    # direct tcl call before i ported this to pythotk
    tk.tcl_call(None, 'wm', 'iconphoto', window.toplevel,
                images.get('logo-200x200'))
