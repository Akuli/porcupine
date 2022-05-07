from porcupine import get_main_window, menubar


def test_switching_themes():
    menu = menubar.get_menu("UI Themes")
    themes_in_menu = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]

    for theme_name in themes_in_menu:
        get_main_window().event_generate(f"<<Menubar:UI Themes/{theme_name}>>")
        get_main_window().update()  # Exposes bugs elsewhere in porcupine
        assert get_main_window().tk.eval("ttk::style theme use") == theme_name
