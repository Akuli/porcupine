# see also: https://github.com/RedFantom/ttkthemes
# TODO: capitalize theme names in menu items?
import functools
import tkinter

from porcupine import actions, settings
import ttkthemes

config = settings.get_section('General')


def on_theme_changed(style, theme_name):
    try:
        style.set_theme(theme_name)
    except tkinter.TclError as e:
        raise settings.InvalidValue(str(e)) from None


# TODO: find a magic way to optimize this? it's not too slow, but it
# could be better
def setup():
    style = ttkthemes.ThemedStyle()

    # https://github.com/RedFantom/ttkthemes/issues/6
    # this does what style.theme_use() should do
    default_theme = style.tk.eval('return $ttk::currentTheme')

    config.add_option('ttk_theme', default_theme, reset=False)
    config.connect('ttk_theme', functools.partial(on_theme_changed, style))
    actions.add_choice("Ttk Themes", sorted(style.get_themes()),
                       var=config.get_var('ttk_theme'))
