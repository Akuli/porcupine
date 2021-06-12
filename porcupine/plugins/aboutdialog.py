"""Display the "About Porcupine" button in the "Help" menu."""
from __future__ import annotations

import functools
import itertools
import os
import pathlib
import re
import subprocess
import sys
import tkinter
import webbrowser
from tkinter import ttk
from typing import Any, List, Match, Union

from porcupine import __version__ as porcupine_version
from porcupine import get_main_window, images, menubar, plugins, textwidget, utils

_BORING_TEXT = """
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
"""


def show_huge_logo(junk: object = None) -> None:
    # Web browsers are good at displaying large images, and webbrowser.open
    # actually tries xdg-open first. So, if you're on linux and you have an
    # image viewer installed, this should launch that. I guess it just opens up
    # web browser on other platforms.
    webbrowser.open((images.images_dir / "logo.gif").as_uri())


class _AboutDialogContent(ttk.Frame):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        # TODO: calculate height automagically, instead of hard-coding
        self._textwidget = textwidget.create_passive_text_widget(self, width=60, height=25)
        self._textwidget.pack(fill="both", expand=True, padx=5, pady=5)

        if sum(self.winfo_rgb(self._textwidget["bg"])) / 3 > 0x7FFF:
            # Bright background
            link_color = "blue"
        else:
            # Dark background
            link_color = "DarkOrange1"

        # http://effbot.org/zone/tkinter-text-hyperlink.htm
        # that tutorial is almost as old as i am, but it's still usable
        self._textwidget.tag_config("link", foreground=link_color, underline=True)
        self._textwidget.tag_bind("link", "<Enter>", self._enter_link)
        self._textwidget.tag_bind("link", "<Leave>", self._leave_link)
        self._link_tag_names = map("link-{}".format, itertools.count())

        self._textwidget.config(state="normal")
        for text_chunk in _BORING_TEXT.strip().split("\n\n"):
            self._add_minimal_markdown(text_chunk)
            self._textwidget.insert("end", "\n\n")
        self._add_directory_link(
            "Porcupine is installed to", pathlib.Path(__file__).absolute().parent.parent.parent
        )
        self._add_directory_link("You can install plugins to", pathlib.Path(plugins.__path__[0]))
        self._textwidget.config(state="disabled")

        label = ttk.Label(self, image=images.get("logo-200x200"), cursor="hand2")
        label.pack(anchor="e")
        utils.set_tooltip(label, "Click to view in full size")
        label.bind("<Button-1>", show_huge_logo, add=True)

    def _add_minimal_markdown(self, text: str) -> None:
        parts: List[Union[str, Match[str]]] = []

        previous_end = 0
        for link in re.finditer(r"\[(.+?)\]\((.+?)\)", text):
            parts.append(text[previous_end : link.start()])
            parts.append(link)
            previous_end = link.end()
        parts.append(text[previous_end:])

        for part in parts:
            if isinstance(part, str):
                self._textwidget.insert("end", part)
            else:
                # a link
                text, href = part.groups()
                tag = next(self._link_tag_names)
                self._textwidget.tag_bind(  # bindcheck: ignore
                    tag, "<Button-1>", functools.partial(self._open_link, href)
                )
                self._textwidget.insert("end", text, ["link", tag])

    def _add_directory_link(self, description: str, path: pathlib.Path) -> None:
        tag = next(self._link_tag_names)
        self._textwidget.insert("end", description + " ")
        self._textwidget.insert("end", str(path), ["link", tag])
        self._textwidget.tag_bind(tag, "<Button-1>", functools.partial(self._open_directory, path))
        self._textwidget.insert("end", ".\n")

    def _enter_link(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        self._textwidget.config(cursor="hand2")

    def _leave_link(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        self._textwidget.config(cursor="")

    def _open_link(self, href: str, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        webbrowser.open(href)

    def _open_directory(self, path: pathlib.Path, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        assert path.is_dir()
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


def show_about_dialog() -> None:
    dialog = tkinter.Toplevel()
    content = _AboutDialogContent(dialog)
    content.pack(fill="both", expand=True)

    content.update()  # make sure that the winfo stuff works
    dialog.minsize(content.winfo_reqwidth(), content.winfo_reqheight())
    dialog.title(f"About Porcupine {porcupine_version}")
    dialog.transient(get_main_window())
    dialog.wait_window()


def setup() -> None:
    menubar.get_menu("Help").add_command(label="About Porcupine", command=show_about_dialog)
