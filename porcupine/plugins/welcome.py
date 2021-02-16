"""Display a welcome message when there are no tabs."""
from __future__ import annotations

import re
import tkinter
from tkinter import ttk

from porcupine import get_tab_manager, images, tabs, utils

# Key bindings are included in the message
setup_after = ['keybindings']


def get_message() -> str:
    result = f"""
To get started, create a new file by pressing {utils.get_binding('<<Menubar:File/New File>>')}
or open an existing file by pressing {utils.get_binding('<<Menubar:File/Open>>')}.
You can save the file with {utils.get_binding('<<Menubar:File/Save>>')}
and then run it by pressing {utils.get_binding('<<Menubar:Run/Run>>')}.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

    # replace single newlines with spaces
    return re.sub(r'(.)\n(.)', r'\1 \2', result.strip())


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
            self._frame, text=get_message(), font=('', 15, ''))
        self.message_label.pack(pady=BORDER_SIZE)

        self._on_tab_closed()

    def update_wraplen(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # images.get('logo-200x200').width() is always 200, but hard-coding is bad
        self.title_label.config(wraplength=(
            event.width - images.get('logo-200x200').width() - BORDER_SIZE))
        self.message_label.config(wraplength=(event.width - 2*BORDER_SIZE))

    def on_new_tab(self, tab: tabs.Tab) -> None:
        self._frame.pack_forget()
        tab.bind('<Destroy>', self._on_tab_closed, add=True)

    def _on_tab_closed(self, junk: object = None) -> None:
        if not get_tab_manager().tabs():
            self._frame.pack(fill='both', expand=True)


def setup() -> None:
    displayer = WelcomeMessageDisplayer()
    get_tab_manager().bind('<Configure>', displayer.update_wraplen, add=True)
    get_tab_manager().add_tab_callback(displayer.on_new_tab)
