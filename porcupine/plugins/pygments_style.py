"""Add an action for choosing the Pygments style."""

import threading

import pygments.styles
import teek as tk

from porcupine import actions, get_main_window, settings

# TODO: here's old code that created colored menu items, add it back
#        style = pygments.styles.get_style_by_name(name)
#        bg = style.background_color
#
#        # styles have a style_for_token() method, but only iterating
#        # is documented :( http://pygments.org/docs/formatterdevelopment/
#        # i'm using iter() to make sure that dict() really treats
#        # the style as an iterable of pairs instead of some other
#        # metaprogramming fanciness
#        fg = None
#        style_infos = dict(iter(style))
#        for token in [pygments.token.String, pygments.token.Text]:
#            if style_infos[token]['color'] is not None:
#                fg = '#' + style_infos[token]['color']
#                break
#        if fg is None:
#            # do like textwidget.ThemedText._set_style does
#            fg = (getattr(style, 'default_style', '') or
#                  utils.invert_color(bg))
#
#        options['foreground'] = options['activebackground'] = fg
#        options['background'] = options['activeforeground'] = bg
#
#        menubar.get_menu("Color Themes").add_radiobutton(**options)


@tk.make_thread_safe
def on_styles_loaded(styles):
    config = settings.get_section('General')
    actions.add_choice("Color Styles", styles,
                       var=config.get_var('pygments_style'))


# threading this gives a significant speed improvement on startup
# on this system, setup() took 0.287940 seconds before adding threads
# and 0.000371 seconds after adding threads
def load_styles_to_list():
    styles = list(pygments.styles.get_all_styles())    # slow
    styles.sort()
    on_styles_loaded(styles)


def setup():
    thread = threading.Thread(target=load_styles_to_list)
    thread.daemon = True     # i don't care wtf happens to this
    thread.start()
