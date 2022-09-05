"""Full Screen button in the View menu."""

from porcupine import get_main_window, menubar


def set_fullscreened(value: bool) -> None:
    get_main_window().attributes("-fullscreen", value)


def get_fullscreened() -> bool:
    return bool(get_main_window().attributes("-fullscreen"))


def setup() -> None:
    menubar.get_menu("View").add_command(
        label="Toggle Full Screen", command=lambda: set_fullscreened(not get_fullscreened())
    )
