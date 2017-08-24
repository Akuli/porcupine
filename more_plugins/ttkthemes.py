# see also: https://github.com/RedFantom/ttkthemes
import functools

import porcupine
import ttkthemes


def setup():
    style = ttkthemes.ThemedStyle()
    for theme in sorted(style.get_themes()):
        callback = functools.partial(style.set_theme, theme)
        porcupine.add_action(callback, 'Ttk Themes/%s' % theme)
