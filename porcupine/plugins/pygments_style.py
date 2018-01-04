"""Add an action for choosing the Pygments style."""

import pygments.styles

from porcupine import actions, settings

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


def setup():
    # TODO: loading the styles takes a long time on startup... try to
    # make it asynchronous without writing too complicated code?
    config = settings.get_section('General')
    actions.add_choice(
        "Color Styles", sorted(pygments.styles.get_all_styles()),
        var=config.get_var('pygments_style'))
