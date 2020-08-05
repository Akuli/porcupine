"""Add an action for choosing the Pygments style."""

import threading
import tkinter
import typing

import pygments.styles      # type: ignore

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


# threading this gives a significant speed improvement on startup
# on this system, setup() took 0.287940 seconds before adding threads
# and 0.000371 seconds after adding threads
def load_styles_to_list(target_list: typing.List[str]) -> None:
    target_list.extend(pygments.styles.get_all_styles())    # slow
    target_list.sort()


def setup() -> None:
    styles: typing.List[str] = []
    thread = threading.Thread(target=load_styles_to_list, args=[styles])
    thread.daemon = True     # i don't care wtf happens to this
    thread.start()

    def check_if_it_finished() -> None:
        if thread.is_alive():
            get_main_window().after(200, check_if_it_finished)
        else:
            var = tkinter.StringVar(value=settings.get('pygments_style', str))

            def settings2var(event: tkinter.Event) -> None:
                # toplevel widgets get notified from their children's events, don't want that here
                if event.widget == get_main_window():
                    var.set(settings.get('pygments_style', str))

            def var2settings(*junk: str) -> None:
                settings.set('pygments_style', var.get())

            # this doesn't recurse infinitely because <<SettingsChanged:bla>>
            # gets generated only when the setting actually changes
            get_main_window().bind('<<SettingsChanged:pygments_style>>', settings2var, add=True)
            var.trace_add('write', var2settings)
            actions.add_choice("Color Styles", styles, var=var)

    get_main_window().after(200, check_if_it_finished)
