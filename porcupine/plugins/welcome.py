"""Display a welcome message when there are no tabs."""
from __future__ import annotations

import re
import tkinter
from tkinter import ttk

from porcupine import get_tab_manager, images, tabs, utils

# Key bindings are included in the message
setup_after = ["keybindings"]


def get_message() -> str:
    result = f"""
To get started, create a new file by pressing {utils.get_binding('<<Menubar:File/New File>>')}
or open an existing file by pressing {utils.get_binding('<<Menubar:File/Open>>')}.
You can save the file with {utils.get_binding('<<Menubar:File/Save>>')}
and then run it by pressing {utils.get_binding('<<Menubar:Run/Repeat previous command>>')}.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

    # replace single newlines with spaces
    return re.sub(r"(.)\n(.)", r"\1 \2", result.strip())


MARGIN = 30  # pixels


# this is a class just to avoid globals (lol)
class WelcomeMessageDisplayer:
    def __init__(self) -> None:
        self.big_frame = ttk.Frame(
            get_tab_manager(),
            name="welcome_frame",
            padding=(*(MARGIN,) * 2, 0, 0),  # readability counts XD
        )
        self.big_frame.columnconfigure(0, weight=1)

        self.welcome_label = ttk.Label(
            self.big_frame, text="Welcome to Porcupine!", font=("", 25, "bold")
        )
        self.welcome_label.grid(row=0, column=0)

        ttk.Label(self.big_frame, image=images.get("logo-200x200")).grid(row=0, column=1)

        self.message_label = ttk.Label(
            self.big_frame, text=get_message(), font=("", 15, ""), name="message"
        )
        self.message_label.grid(row=1, column=0, sticky="we", columnspan=2, pady=MARGIN)

        print(self.welcome_label.grid_info())
        print(self.message_label.grid_info())

        self._on_tab_closed()

    def update_wraplen(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # images.get('logo-200x200').width() is always 200, but hard-coding is bad
        self.welcome_label.config(
            wraplength=(event.width - images.get("logo-200x200").width() - MARGIN)
        )
        self.message_label.config(wraplength=(event.width - 2 * MARGIN))

    def on_new_tab(self, tab: tabs.Tab) -> None:
        self.big_frame.pack_forget()
        tab.bind("<Destroy>", self._on_tab_closed, add=True)

    def _on_tab_closed(self, junk: object = None) -> None:
        if not get_tab_manager().tabs():
            self.big_frame.pack(fill="both", expand=True)


def setup() -> None:
    displayer = WelcomeMessageDisplayer()
    get_tab_manager().bind("<Configure>", displayer.update_wraplen, add=True)
    get_tab_manager().add_tab_callback(displayer.on_new_tab)
