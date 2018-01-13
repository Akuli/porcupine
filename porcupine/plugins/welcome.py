"""Simple welcome message."""

import re
from tkinter import ttk

from porcupine import get_tab_manager, images, utils


RAW_MESSAGE = """
Porcupine is a simple, beginner-friendly editor. If you ever used
anything like Notepad, Microsoft Word or LibreOffice Writer before, you
will feel right at home.

To get started, create a new file by pressing Ctrl+N or open an existing
file by pressing Ctrl+O. You can save the file with Ctrl+S or run a
program by pressing F5.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

# replace single newlines with spaces
MESSAGE = re.sub(r'(.)\n(.)', r'\1 \2', RAW_MESSAGE.strip())

BORDER_SIZE = 30    # pixels


# this is a class just to avoid globals (lol)
class WelcomeMessageDisplayer:

    def __init__(self):
        # make it about 200 pixels wide by taking every magic'th pixel
        magic = images.get('logo').width() // 200
        self._image = images.get('logo').subsample(magic)
        self._frame = ttk.Frame(get_tab_manager())

        # pad only on left side so the image goes as far right as possible
        top = ttk.Frame(self._frame)
        top.pack(fill='x', padx=(BORDER_SIZE, 0))
        ttk.Label(top, image=self._image).pack(side='right')

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

    def update_wraplen(self, event):
        self.title_label['wraplength'] = (
            event.width - self._image.width() - BORDER_SIZE)
        self.message_label['wraplength'] = event.width - 2*BORDER_SIZE  # noqa

    def on_new_tab(self, event):
        self._frame.pack_forget()
        event.data_widget.bind('<Destroy>', self._on_tab_closed, add=True)

    def _on_tab_closed(self, event=None):
        if not get_tab_manager().tabs():
            self._frame.pack(fill='both', expand=True)


def setup():
    displayer = WelcomeMessageDisplayer()
    get_tab_manager().bind('<Configure>', displayer.update_wraplen, add=True)
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>',
                         displayer.on_new_tab, add=True)
