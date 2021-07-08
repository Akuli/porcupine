"""Change the look of Porcupine's GUI.

This plugin doesn't do anything to the colors used in the main editing area.
Those are handled by pygments_style and highlight plugins.
"""
# TODO: capitalize theme names in menu items?
import tkinter

import ttkthemes  # type: ignore[import]

from porcupine import get_main_window, menubar, settings


def setup() -> None:
    style = ttkthemes.ThemedStyle()

    if get_main_window().tk.call("tk", "windowingsystem") == "x11":
        # Default theme sucks on linux
        settings.add_option("ttk_theme", "black")
    else:
        settings.add_option("ttk_theme", style.theme_use())

    var = tkinter.StringVar()
    for name in sorted(style.get_themes()):
        menubar.get_menu("Ttk Themes").add_radiobutton(label=name, value=name, variable=var)

    # Connect style and var
    var.trace_add("write", lambda *junk: style.set_theme(var.get()))

    # Connect var and settings
    get_main_window().bind(
        "<<SettingChanged:ttk_theme>>",
        lambda event: var.set(settings.get("ttk_theme", str)),
        add=True,
    )
    var.set(settings.get("ttk_theme", str))
    var.trace_add("write", lambda *junk: settings.set_("ttk_theme", var.get()))
