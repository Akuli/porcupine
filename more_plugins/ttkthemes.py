# see also: https://github.com/RedFantom/ttkthemes
import functools
import tkinter

from porcupine import menubar
import ttkthemes


def on_theme_changed(style, var, *stupid_junk):
    style.set_theme(var.get())


def setup():
    style = ttkthemes.ThemedStyle()
    theme_var = tkinter.StringVar()

    menu = menubar.get_menu('Ttk Themes')
    for theme in sorted(style.get_themes()):
        menu.add_radiobutton(label=theme.title(), value=theme,
                             variable=theme_var)

    theme_var.trace('w', functools.partial(on_theme_changed, style, theme_var))

    # https://github.com/RedFantom/ttkthemes/issues/6
    # this does what theme_var.set(style.theme_use()) should do
    style.tk.eval('set %s $ttk::currentTheme' % theme_var)
