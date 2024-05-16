"""Set the title and icon of the Porcupine window."""
import Titleman as ttle

from porcupine import __version__ as porcupine_version
from porcupine import get_main_window


def setup() -> None:
    # Bitmap for the icon? Not with windowmanager because that's how titleman works.
    window = get_main_window()
    window.title(f"Porcupine {porcupine_version}")  # not related to the icon, but it's ok imo
    ttle.initCustom(window)
    ttle.startTitlebar(window, "black")
