"""Simple welcome message."""

import re
from tkinter import ttk

from porcupine import get_tab_manager, utils


RAW_MESSAGE = """
Porcupine is a simple, beginner-friendly editor for writing Python code.
If you ever used anything like Notepad, Microsoft Word or LibreOffice
Writer before, you will feel right at home.

You can create a new file by pressing Ctrl+N or open an existing file by
pressing Ctrl+O. The file name will be displayed in red if the file has
been changed and you can save the file with Ctrl+S. Then you can run the
file by pressing F5.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

# replace single newlines with spaces
MESSAGE = re.sub(r'(.)\n(.)', r'\1 \2', RAW_MESSAGE.strip())


# this is a class just to avoid globals (lol)
class WelcomeMessageDisplayer:

    def __init__(self):
        self._message = ttk.Frame(get_tab_manager())
        self._message.place(relx=0.5, rely=0.5, anchor='center')
        ttk.Label(self._message, text="Welcome to Porcupine!\n",
                  font=('', 16, '')).pack()
        ttk.Label(self._message, text=MESSAGE, font=('', 14, '')).pack()

    def update_wraplen(self, event):
        for label in self._message.winfo_children():
            label['wraplength'] = event.width * 0.9     # small borders

    def on_new_tab(self, event):
        self._message.place_forget()
        event.data_widget.bind('<Destroy>', self._on_tab_closed, add=True)

    def _on_tab_closed(self, event):
        if not get_tab_manager().tabs:
            self._message.place(relx=0.5, rely=0.5, anchor='center')


def setup():
    displayer = WelcomeMessageDisplayer()
    get_tab_manager().bind('<Configure>', displayer.update_wraplen, add=True)
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>',
                         displayer.on_new_tab, add=True)
