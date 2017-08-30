# see also: https://github.com/RedFantom/ttkthemes
import functools
import tkinter

from porcupine import menubar, settings
import ttkthemes

config = settings.get_section('General')


def on_theme_changed(style, theme_name):
    try:
        style.set_theme(theme_name)
    except tkinter.TclError as e:
        raise settings.InvalidValue(str(e)) from None


def setup():
    style = ttkthemes.ThemedStyle()

    # https://github.com/RedFantom/ttkthemes/issues/6
    # this does what style.theme_use() should do
    default_theme = style.tk.eval('return $ttk::currentTheme')

    config.add_option('ttk_theme', default_theme, reset=False)
    config.connect('ttk_theme', functools.partial(on_theme_changed, style),
                   run_now=True)

    menu = menubar.get_menu('Ttk Themes')
    for theme in sorted(style.get_themes()):
        menu.add_radiobutton(label=theme.title(), value=theme,
                             variable=config.get_var('ttk_theme'))

    theme_var.trace('w', functools.partial(on_theme_changed, style, theme_var))
