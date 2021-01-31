"""More Ttk themes: https://github.com/RedFantom/ttkthemes"""
# TODO: capitalize theme names in menu items?
import tkinter

import ttkthemes  # type: ignore[import]

from porcupine import menubar, settings, get_main_window


def setup() -> None:
    style = ttkthemes.ThemedStyle()
    settings.add_option('ttk_theme', style.theme_use())

    var = tkinter.StringVar()
    for name in sorted(style.get_themes()):
        menubar.get_menu("Ttk Themes").add_radiobutton(label=name, value=name, variable=var)

    # Connect style and var
    var.trace_add('write', lambda *junk: style.set_theme(var.get()))

    # Connect var and settings
    get_main_window().bind('<<SettingChanged:ttk_theme>>', (
        lambda event: var.set(settings.get('ttk_theme', str))
    ), add=True)
    var.set(settings.get('ttk_theme', str))
    var.trace_add('write', lambda *junk: settings.set('ttk_theme', var.get()))
