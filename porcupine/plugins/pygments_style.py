"""Display a "Color Styles" menu."""
from __future__ import annotations

import threading
import tkinter

from pygments import styles, token

from porcupine import get_main_window, get_tab_manager, menubar, settings, utils


def get_colors(style_name: str) -> tuple[str, str]:
    style = styles.get_style_by_name(style_name)
    bg = style.background_color

    # style_names have a style_for_token() method, but only iterating
    # is documented :( http://pygments.org/docs/formatterdevelopment/
    # i'm using iter() to make sure that dict() really treats
    # the style as an iterable of pairs instead of some other
    # metaprogramming fanciness
    style_infos = dict(iter(style))

    fg = style_infos[token.String]["color"] or style_infos[token.Text]["color"]
    if fg:
        # style_infos doesn't contain leading '#' for whatever reason
        fg = "#" + fg
    else:
        # do like textutils.use_pygments_theme does
        fg = getattr(style, "default_style", "") or utils.invert_color(bg)

    return (fg, bg)


# threading this gives a significant speed improvement on startup
# on this system, setup() took 0.287940 seconds before adding threads
# and 0.000371 seconds after adding threads
def load_style_names_to_list(target_list: list[str]) -> None:
    target_list.extend(styles.get_all_styles())  # slow
    target_list.sort()


def setup() -> None:
    style_names: list[str] = []
    thread = threading.Thread(target=load_style_names_to_list, args=[style_names])
    thread.daemon = True  # i don't care wtf happens to this
    thread.start()

    def check_if_it_finished() -> None:
        if thread.is_alive():
            get_main_window().after(200, check_if_it_finished)
            return

        var = tkinter.StringVar(value=settings.get("pygments_style", str))

        def settings2var(event: tkinter.Event[tkinter.Misc]) -> None:
            var.set(settings.get("pygments_style", str))

        def var2settings(*junk: str) -> None:
            settings.set_("pygments_style", var.get())

        # this doesn't recurse infinitely because <<SettingChanged:bla>>
        # gets generated only when the setting actually changes
        get_tab_manager().bind("<<SettingChanged:pygments_style>>", settings2var, add=True)
        var.trace_add("write", var2settings)

        for style_name in style_names:
            fg, bg = get_colors(style_name)
            menubar.get_menu("Color Styles").add_radiobutton(
                label=style_name,
                value=style_name,
                variable=var,
                foreground=fg,
                background=bg,
                # swapped colors
                activeforeground=bg,
                activebackground=fg,
            )

    get_main_window().after(200, check_if_it_finished)
