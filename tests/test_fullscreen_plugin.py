import os

import pytest

from porcupine import get_main_window
from porcupine.menubar import get_menu

headless = os.getenv("GITHUB_ACTIONS") == "true" or "xvfb" in os.getenv("XAUTHORITY", "")


pytestmark = pytest.mark.skipif(headless, reason="Does not work in headless environments")


def test_basic(wait_until):
    assert not get_main_window().attributes("-fullscreen")

    get_menu("View").invoke("Toggle Full Screen")
    wait_until(lambda: bool(get_main_window().attributes("-fullscreen")))

    get_menu("View").invoke("Toggle Full Screen")
    wait_until(lambda: not get_main_window().attributes("-fullscreen"))


# Window managers can toggle full-screen-ness without going through our menubar
def test_toggled_without_menu_bar(wait_until):
    get_main_window().attributes("-fullscreen", 1)
    wait_until(lambda: bool(get_main_window().attributes("-fullscreen")))

    get_menu("View").invoke("Toggle Full Screen")
    wait_until(lambda: not get_main_window().attributes("-fullscreen"))
