"""Change the look of Porcupine's GUI.

This plugin doesn't do anything to the colors used in the main editing area.
Those are handled by pygments_style and highlight plugins.

You also need to disable the `ttk_themes` plugin for this to work well.
"""

import sv_ttk  # type: ignore

from porcupine import get_main_window, get_tab_manager, settings
from porcupine.settings import global_settings


def set_theme(theme: str) -> None:
    sv_ttk.set_theme(theme.lower())
    main_window = get_main_window()
    # TODO: the next 3 lines are a hack?
    # If they are really needed, why it isn't in sv-ttk by default?
    main_window.option_add("*Text.highlightThickness", "0")
    main_window.option_add("*Text.borderWidth", "2")
    main_window.option_add("*Text.relief", "solid")


def setup() -> None:
    global_settings.add_option("sv_theme", "Dark")
    settings.add_combobox("sv_theme", "UI theme", values=["Dark", "Light"], state="readonly")
    set_theme(global_settings.get("sv_theme", str))

    get_tab_manager().bind(
        "<<GlobalSettingChanged:sv_theme>>",
        lambda event: set_theme(global_settings.get("sv_theme", str)),
        add=True,
    )
