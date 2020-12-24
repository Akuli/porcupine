"""Display a "Color Styles" menu."""

import threading
import tkinter
from typing import List, Optional, Tuple

from pygments import styles, token      # type: ignore

from porcupine import get_main_window, get_tab_manager, menubar, settings, utils


def get_colors(style_name: str) -> Tuple[str, str]:
    style = styles.get_style_by_name(style_name)
    bg: str = style.background_color

    # style_names have a style_for_token() method, but only iterating
    # is documented :( http://pygments.org/docs/formatterdevelopment/
    # i'm using iter() to make sure that dict() really treats
    # the style as an iterable of pairs instead of some other
    # metaprogramming fanciness
    fg: Optional[str] = None
    style_infos = dict(iter(style))

    for tokentype in [token.String, token.Text]:
        if style_infos[tokentype]['color'] is not None:
            fg = '#' + style_infos[tokentype]['color']
            break

    if fg is None:
        # do like textwidget.use_pygments_theme does
        fg = getattr(style, 'default_style', '') or utils.invert_color(bg)

    return (fg, bg)


# threading this gives a significant speed improvement on startup
# on this system, setup() took 0.287940 seconds before adding threads
# and 0.000371 seconds after adding threads
def load_style_names_to_list(target_list: List[str]) -> None:
    target_list.extend(styles.get_all_styles())    # slow
    target_list.sort()


def setup() -> None:
    style_names: List[str] = []
    thread = threading.Thread(target=load_style_names_to_list, args=[style_names])
    thread.daemon = True     # i don't care wtf happens to this
    thread.start()

    def check_if_it_finished() -> None:
        if thread.is_alive():
            get_main_window().after(200, check_if_it_finished)
            return

        var = tkinter.StringVar(value=settings.get('pygments_style', str))

        def settings2var(event: 'tkinter.Event[tkinter.Misc]') -> None:
            var.set(settings.get('pygments_style', str))

        def var2settings(*junk: str) -> None:
            settings.set('pygments_style', var.get())

        # this doesn't recurse infinitely because <<SettingChanged:bla>>
        # gets generated only when the setting actually changes
        get_tab_manager().bind('<<SettingChanged:pygments_style>>', settings2var, add=True)
        var.trace_add('write', var2settings)

        for style_name in style_names:
            fg, bg = get_colors(style_name)
            menubar.get_menu("Color Styles").add_radiobutton(
                label=style_name, value=style_name, variable=var,
                foreground=fg, background=bg,
                activeforeground=bg, activebackground=fg,   # swapped colors
            )

    get_main_window().after(200, check_if_it_finished)
