"""Display the "About Porcupine" button in the "Help" menu."""
from __future__ import annotations

import collections
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


def get_link_opener(match: re.Match[str]) -> Callable[[], object]:
    url = match.group(2)
    if url:
        return lambda: webbrowser.open(url)

    path = Path(match.group(1))
    assert path.is_dir(), path

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


class EasterEggs:
    def __init__(self, porcupine_logo: tkinter.Label) -> None:
        self.pic = porcupine_logo
        self.window = porcupine_logo.winfo_toplevel()

    def setup(self) -> None:
        self.setup_easter_egg_1()
        self.setup_easter_egg_2()

    def move(self, dx: int, dy: int) -> None:
        old = self.pic.place_info()
        self.pic.place(x=(int(old['x']) + dx), y=(int(old["y"])+dy))

    def setup_easter_egg_1(self) -> None:
        fall_speed = 0

        def gravity() -> None:
            if not self.pic.winfo_exists():
                return

            nonlocal fall_speed
            self.move(0, fall_speed)
            fall_speed += 4

            if int(self.pic.place_info()["y"]) > 0:
                # land
                self.pic.place(y=0)
            else:
                self.timeout = self.pic.after(round(1000 / 60), gravity)

        def jump() -> str:
            print("jup")
            nonlocal fall_speed
            fall_speed = -50
            gravity()

        self.window.bind("<Left>", (lambda e: self.move(-10, 0)), add=True)
        self.window.bind("<Right>", (lambda e: self.move(10, 0)), add=True)
        self.window.bind("<Up>", (lambda e: jump()), add=True)

    def setup_easter_egg_2(self) -> None:
        buffer = collections.deque(maxlen=3)
        dx = -1
        dy = -1

        def bounce():
            if list(buffer) != list("dvd") or not self.pic.winfo_exists():
                return
            self.timeout = self.pic.after(round(1000 / 60), bounce)

            x_min = -(self.window.winfo_width() - 200)
            y_min = -(self.window.winfo_height() - 200)
            x_max = 0
            y_max = 0

            nonlocal dx,dy
            x = int(self.pic.place_info()['x'])
            y = int(self.pic.place_info()['y'])
            if x < x_min:
                dx = 1
            if x > x_max:
                dx = -1
            if y < y_min:
                dy = 1
            if y > y_max:
                dy = -1

            self.move(2*dx, 2*dy)

        def handle_key(event: tkinter.Event[tkinter.Misc]) -> None:
            buffer.append(event.char)
            bounce()

        self.window.bind("d", handle_key, add=True)
        self.window.bind("v", handle_key, add=True)


def show_about_dialog() -> None:
    dialog = tkinter.Toplevel()
    content_frame = ttk.Frame(dialog)
    content_frame.pack(fill="both", expand=True)

    # TODO: calculate height automagically, instead of hard-coding
    textwidget = textutils.create_passive_text_widget(content_frame, width=60, height=25)
    textwidget.pack(fill="both", expand=True, padx=5, pady=5)

    textwidget.config(state="normal")
    textwidget.insert(
        "end",
        f"""\
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
LICENSE file with it. [Click here](https://github.com/Akuli/porcupine/blob/main/LICENSE) for details.

Porcupine is installed to [{Path(__file__).absolute().parent.parent.parent}]().
You can install plugins to [{plugins.__path__[0]}]().
""",
    )

    regex = r"\[(.+?)\]\((.*?)\)"
    textutils.LinkManager(textwidget, regex, get_link_opener).add_links("1.0", "end")

    ranges = textwidget.tag_ranges("link")
    for start, end in reversed(list(zip(ranges[0::2], ranges[1::2]))):
        match = re.fullmatch(regex, textwidget.get(start, end))
        assert match
        textwidget.replace(start, end, match.group(1), textwidget.tag_names(start))

    textwidget.config(state="disabled")

    if utils.is_bright(textwidget["bg"]):
        link_color = "blue"
    else:
        link_color = "DarkOrange1"
    textwidget.tag_config("link", foreground=link_color, underline=True)

    dialog.update()  # make sure that the winfo stuff works
    width = content_frame.winfo_reqwidth()
    height = content_frame.winfo_reqheight() + 200

    label = ttk.Label(dialog, image=images.get("logo-200x200"), cursor="hand2")
    label.bind("<Button-1>", show_huge_logo, add=True)
    label.place(relx=1, rely=1, anchor="se")
    EasterEggs(label).setup()

    dialog.title(f"About Porcupine {porcupine_version}")
    dialog.transient(get_main_window())
    dialog.minsize(width, height)
    dialog.wait_window()


def setup() -> None:
    menubar.get_menu("Help").add_command(label="About Porcupine", command=show_about_dialog)
