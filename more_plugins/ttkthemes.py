# see also: https://github.com/RedFantom/ttkthemes
import functools

import porcupine
import ttkthemes


def setup():
    # yes, this is needed
    ttkthemes.ThemedStyle()

    # ttkthemes wants me to create a ttkthemes.ThemedTk instead of a sane
    # tkinter.Tk, but i don't like that at all so i need these weird poops
    root = porcupine.get_main_window().nametowidget('.')
    root.img_support = False
    for theme in sorted(ttkthemes.ThemedTk.get_themes(root)):
        callback = functools.partial(ttkthemes.ThemedTk.set_theme, root, theme)
        porcupine.add_action(callback, 'Ttk Themes/%s' % theme)
    del root.img_support
