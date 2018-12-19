"""Simple welcome message."""

import re

import pythotk as tk

from porcupine import get_tab_manager, images

# refuse to run without the geometry plugin because this thing does very weird
# things without it, try it and see to find out
import porcupine.plugins.geometry   # noqa


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
        self._frame = tk.Frame(get_tab_manager())

        # pad only on left side so the image goes as far right as possible
        top = tk.Frame(self._frame)
        top.pack(fill='x', padx=(BORDER_SIZE, 0))
        tk.Label(top, image=images.get('logo-200x200')).pack(side='right')

        # TODO: better way to center the label in its space?
        centerer = tk.Frame(top)
        centerer.pack(fill='both', expand=True)
        self.title_label = tk.Label(centerer, "Welcome to Porcupine!",
                                    font=('', 25, 'bold'))
        self.title_label.place(relx=0.5, rely=0.5, anchor='center')

        self.message_label = tk.Label(self._frame, MESSAGE, font=('', 15, ''))
        self.message_label.pack(pady=BORDER_SIZE)

        self._on_tab_closed()

    def update_wraplen(self, event):
        # images.get('logo-200x200').width is always 200, but
        # hard-coding is bad
        self.title_label.config['wraplength'] = (
            event.width - images.get('logo-200x200').width - BORDER_SIZE)
        self.message_label.config['wraplength'] = event.width - 2 * BORDER_SIZE

    def on_new_tab(self, tab):
        self._frame.pack_forget()
        tab.widget.bind('<Destroy>', self._on_tab_closed)

    def _on_tab_closed(self):
        if not get_tab_manager():
            self._frame.pack(fill='both', expand=True)


def setup():
    displayer = WelcomeMessageDisplayer()
    get_tab_manager().bind('<Configure>', displayer.update_wraplen, event=True)
    get_tab_manager().on_new_tab.connect(displayer.on_new_tab)
