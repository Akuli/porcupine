"""More Ttk themes: https://github.com/RedFantom/ttkthemes"""
# TODO: capitalize theme names in menu items?
import functools
import tkinter

import ttkthemes  # type: ignore[import]

from porcupine import menubar, settings


def on_theme_changed(style: ttkthemes.ThemedStyle, var: tkinter.StringVar, *junk: object) -> None:
    theme_name = var.get()
    style.set_theme(theme_name)
    settings.set('ttk_theme', theme_name)


def setup() -> None:
    style = ttkthemes.ThemedStyle()

    # https://github.com/RedFantom/ttkthemes/issues/6
    # this does what style.theme_use() should do
    default_theme = style.tk.eval('return $ttk::currentTheme')
    settings.add_option('ttk_theme', default_theme)

    var = tkinter.StringVar()
    var.trace_add('write', functools.partial(on_theme_changed, style, var))
    var.set(settings.get('ttk_theme', str))
    for name in sorted(style.get_themes()):
        menubar.get_menu("Ttk Themes").add_radiobutton(label=name, value=name, variable=var)
