"""Simple welcome message."""

import re
import tkinter
from tkinter import ttk

from porcupine import get_tab_manager, images, utils


RAW_MESSAGE = """
To get started, create a new file by pressing Ctrl+N or open an existing
file by pressing Ctrl+O. You can save the file with Ctrl+S and then run it by
pressing F5.

Note that your code won't syntax-highlighted unless you save the file or choose
a filetype from the Filetypes menu.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

# replace single newlines with spaces
MESSAGE = re.sub(r'(.)\n(.)', r'\1 \2', RAW_MESSAGE.strip())

BORDER_SIZE = 30    # pixels


# this is a class just to avoid globals (lol)
class WelcomeMessageDisplayer:

    def __init__(self) -> None:
        self._frame = ttk.Frame(get_tab_manager())

        # pad only on left side so the image goes as far right as possible
        top = ttk.Frame(self._frame)
        top.pack(fill='x', padx=(BORDER_SIZE, 0))
        ttk.Label(top, image=images.get('logo-200x200')).pack(side='right')

        # TODO: better way to center the label in its space?
        centerer = ttk.Frame(top)
        centerer.pack(fill='both', expand=True)
        self.title_label = ttk.Label(
            centerer, text="Welcome to Porcupine!", font=('', 25, 'bold'))
        self.title_label.place(relx=0.5, rely=0.5, anchor='center')

        self.message_label = ttk.Label(
            self._frame, text=MESSAGE, font=('', 15, ''))
        self.message_label.pack(pady=BORDER_SIZE)

        self._on_tab_closed()

    def update_wraplen(self, event: tkinter.Event) -> None:
        assert event.width != '??'

        # images.get('logo-200x200').width() is always 200, but hard-coding is bad
        self.title_label['wraplength'] = (
            event.width - images.get('logo-200x200').width() - BORDER_SIZE)
        self.message_label['wraplength'] = event.width - 2*BORDER_SIZE  # noqa

    def on_new_tab(self, event: utils.EventWithData) -> None:
        self._frame.pack_forget()
        event.data_widget().bind('<Destroy>', self._on_tab_closed, add=True)

    def _on_tab_closed(self, junk: object = None) -> None:
        if not get_tab_manager().tabs():
            self._frame.pack(fill='both', expand=True)


def setup() -> None:
    displayer = WelcomeMessageDisplayer()
    get_tab_manager().bind('<Configure>', displayer.update_wraplen, add=True)
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>',
                         displayer.on_new_tab, add=True)
