from porcupine import get_main_window
from porcupine.settings import global_settings


def test_switching_themes():
    for theme_mode in ("Light", "Dark"):
        global_settings.set(option_name="sv_theme", value=theme_mode)
        get_main_window().update()  # Exposes bugs elsewhere in porcupine
        actual_theme = f"sun-valley-{theme_mode.lower()}"
        assert get_main_window().tk.eval("ttk::style theme use") == actual_theme
