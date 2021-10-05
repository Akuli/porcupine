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

Porcupine is installed to [{Path(__file__).absolute().parent.parent.parent}]().
You can install plugins to [{plugins.__path__[0]}]().
"""


def get_link_opener(match: re.Match[str]) -> Callable[[], object]:
    url = match.group(2)
    if url:
        return lambda: webbrowser.open(url)

    path = Path(match.group(1))
    assert path.is_dir()

    # early returns don't work https://github.com/python/mypy/issues/10773
    if sys.platform == "win32":
        return lambda: os.startfile(path)
    elif sys.platform == "darwin":
        return lambda: subprocess.Popen(["open", path])
    else:
        return lambda: subprocess.Popen(["xdg-open", path])


def show_huge_logo(junk: object = None) -> None:
    # Web browsers are good at displaying large images, and webbrowser.open
    # actually tries xdg-open first. So, if you're on linux and you have an
    # image viewer installed, this should launch that. I guess it just opens up
    # web browser on other platforms.
    webbrowser.open((images.images_dir / "logo.gif").as_uri())


def show_about_dialog() -> None:
    dialog = tkinter.Toplevel()
    content_frame = ttk.Frame(dialog)
    content_frame.pack(fill="both", expand=True)

    # TODO: calculate height automagically, instead of hard-coding
    textwidget = textutils.create_passive_text_widget(content_frame, width=60, height=25)
    textwidget.pack(fill="both", expand=True, padx=5, pady=5)

    textwidget.config(state="normal")
    textutils.LinkManager(
        textwidget,
        r"\[(.+?)\]\((.*?)\)",
        get_link_opener,
        get_text=(lambda m: m.group(1)),
    ).append_text(BORING_TEXT.strip() + "\n\n")
    textwidget.config(state="disabled")

    if utils.is_bright(textwidget["bg"]):
        link_color = "blue"
    else:
        link_color = "DarkOrange1"
    textwidget.tag_config("link", foreground=link_color, underline=True)

    label = ttk.Label(content_frame, image=images.get("logo-200x200"), cursor="hand2")
    label.pack(anchor="e")
    label.bind("<Button-1>", show_huge_logo, add=True)

    dialog.update()  # make sure that the winfo stuff works
    dialog.minsize(content_frame.winfo_reqwidth(), content_frame.winfo_reqheight())
    dialog.title(f"About Porcupine {porcupine_version}")
    dialog.transient(get_main_window())
    dialog.wait_window()


def setup() -> None:
    menubar.get_menu("Help").add_command(label="About Porcupine", command=show_about_dialog)
