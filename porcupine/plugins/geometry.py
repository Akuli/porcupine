"""Remember the size and location of the Porcupine window."""
import tkinter

from porcupine import get_main_window, settings


def save_geometry(event: 'tkinter.Event[tkinter.Misc]') -> None:
    assert isinstance(event.widget, (tkinter.Tk, tkinter.Toplevel))
    settings.set_('default_geometry', event.widget.geometry())


def setup() -> None:
    settings.add_option('default_geometry', '650x600')
    get_main_window().geometry(settings.get('default_geometry', str))
    get_main_window().bind('<<PorcupineQuit>>', save_geometry, add=True)
