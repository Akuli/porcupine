"""Remember the size and location of the Porcupine window."""
from __future__ import annotations

import re
import tkinter

from porcupine import get_main_window, settings


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
        and y <= get_main_window().winfo_screenheight()
    )


def save_geometry(event: tkinter.Event[tkinter.Misc]) -> None:
    assert isinstance(event.widget, (tkinter.Tk, tkinter.Toplevel))
    settings.set_("default_geometry", event.widget.geometry())


def setup() -> None:
    settings.add_option("default_geometry", "650x600")
    get_main_window().bind("<<PorcupineQuit>>", save_geometry, add=True)

    geometry = settings.get("default_geometry", str)
    if not geometry_is_within_screen(geometry):
        geometry = geometry.split("+")[0]  # size only, discard location
    get_main_window().geometry(geometry)
