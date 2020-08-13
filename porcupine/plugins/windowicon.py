"""Set the title and icon of the Porcupine window."""
from porcupine import get_main_window, images


def setup() -> None:
    window = get_main_window()
    window.title("Porcupine")    # not related to the icon, but it's ok imo
    window.tk.call('wm', 'iconphoto', window, images.get('logo-200x200'))
