"""Remember the size and location of the Porcupine window."""
from __future__ import annotations

import re

from porcupine import add_quit_callback, get_main_window
from porcupine.settings import global_settings


def geometry_is_within_screen(geometry: str) -> bool:
    match = re.fullmatch(r"(.*)x(.*)\+(.*)\+(.*)", geometry)
    if match is None:
        # Does not specify location, size only
        return True

    width, height, x, y = map(int, match.groups())
    return (
        x >= 0
        and x + width <= get_main_window().winfo_screenwidth()
        and y >= 0
        and y + height <= get_main_window().winfo_screenheight()
    )


def save_geometry() -> bool:
    global_settings.set("default_geometry", get_main_window().geometry())
    return True


def setup() -> None:
    global_settings.add_option("default_geometry", "650x600")
    add_quit_callback(save_geometry)

    geometry = global_settings.get("default_geometry", str)
    if not geometry_is_within_screen(geometry):
        geometry = geometry.split("+")[0]  # size only, discard location
    get_main_window().geometry(geometry)
