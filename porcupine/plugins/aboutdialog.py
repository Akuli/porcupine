"""Display the "About Porcupine" button in the "Help" menu."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tkinter
import webbrowser
from pathlib import Path
from tkinter import ttk
from typing import Callable

from porcupine import __version__ as porcupine_version
from porcupine import get_main_window, images, menubar, plugins, textutils, utils

_install_path = Path(__file__).absolute().parent.parent.parent
_plugin_path = Path(plugins.__path__[0])

BORING_TEXT = f"""
Porcupine is a simple but powerful and configurable text editor written in \
Python using the notorious tkinter GUI library. It started as a \
proof-of-concept of a somewhat good editor written in tkinter, but nowadays \
it's a tool I use at work every day.

I'm [Akuli](https://github.com/Akuli), and I wrote most of Porcupine. See \
[the contributor \
page](https://github.com/Akuli/porcupine/graphs/contributors) for details.

Links:
\N{bullet} [Porcupine Wiki](https://github.com/Akuli/porcupine/wiki)
\N{bullet} [Porcupine on GitHub](https://github.com/Akuli/porcupine)
\N{bullet} [Plugin API documentation for Python programmers](https://akuli.github.io/porcupine/)

Porcupine is available under the MIT license. It means that you can do \
pretty much anything you want with it as long as you distribute the \
LICENSE file with it. [Click here](https://github.com/Akuli/porcupine/blob/master/LICENSE) for details.

Porcupine is installed to [{_install_path}]({_install_path}).
You can install plugins to [{_plugin_path}]({_plugin_path}).
"""


def show_huge_logo(junk: object = None) -> None:
    # Web browsers are good at displaying large images, and webbrowser.open
    # actually tries xdg-open first. So, if you're on linux and you have an
    # image viewer installed, this should launch that. I guess it just opens up
    # web browser on other platforms.
    webbrowser.open((images.images_dir / "logo.gif").as_uri())


class AboutDialogContent(ttk.Frame):
    def __init__(self, dialog: tkinter.Toplevel) -> None:
        super().__init__(dialog)

        # TODO: calculate height automagically, instead of hard-coding
        self._textwidget = textutils.create_passive_text_widget(self, width=60, height=25)
        self._textwidget.pack(fill="both", expand=True, padx=5, pady=5)

        self._textwidget.config(state="normal")
        textutils.LinkManager(
            self._textwidget,
            r"\[(.+?)\]\((.+?)\)",
            self._get_link_opener,
            get_text=(lambda m: m.group(1)),
        ).append_text(BORING_TEXT.strip() + "\n\n")
        self._textwidget.config(state="disabled")

        if utils.is_bright(self._textwidget["bg"]):
            link_color = "blue"
        else:
            link_color = "DarkOrange1"
        self._textwidget.tag_config("link", foreground=link_color, underline=True)

        label = ttk.Label(self, image=images.get("logo-200x200"), cursor="hand2")
        label.pack(anchor="e")
        label.bind("<Button-1>", show_huge_logo, add=True)

    def _get_link_opener(self, match: re.Match[str]) -> Callable[[], object]:
        url_or_path = match.group(2)
        if url_or_path.startswith("https://"):
            return lambda: webbrowser.open(url_or_path)

        path = Path(url_or_path)
        assert path.is_dir()
        if sys.platform == "win32":
            return lambda: os.startfile(path)
        if sys.platform == "darwin":
            return lambda: subprocess.Popen(["open", path])
        return lambda: subprocess.Popen(["xdg-open", path])


def show_about_dialog() -> None:
    dialog = tkinter.Toplevel()
    content = AboutDialogContent(dialog)
    content.pack(fill="both", expand=True)

    content.update()  # make sure that the winfo stuff works
    dialog.minsize(content.winfo_reqwidth(), content.winfo_reqheight())
    dialog.title(f"About Porcupine {porcupine_version}")
    dialog.transient(get_main_window())
    dialog.wait_window()


def setup() -> None:
    menubar.get_menu("Help").add_command(label="About Porcupine", command=show_about_dialog)
