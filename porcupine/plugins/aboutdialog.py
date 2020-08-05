import functools
import itertools
import re
import tkinter
from tkinter import ttk
from typing import Any, List, Match, Optional, Union
import webbrowser

from porcupine import actions, dirs, get_main_window, images, utils
from porcupine import __version__ as porcupine_version


_BORING_TEXT = """
This is porcupine {version}.

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
\N{bullet} [Plugin API documentation for Python \
programmers](https://akuli.github.io/porcupine/)

Porcupine is available under the MIT license. It means that you can do \
pretty much anything you want with it as long as you distribute the \
LICENSE file with it. [Click \
here](https://github.com/Akuli/porcupine/blob/master/LICENSE) for details.
""".format(version=porcupine_version)


def show_huge_logo(junk: object = None) -> None:
    path = dirs.installdir / 'images' / 'logo.gif'
    assert path.is_file()

    # Web browsers are good at displaying large images, and webbrowser.open
    # actually tries xdg-open first. So, if you're on linux and you have an
    # image viewer installed, this should launch that. I guess it just opens up
    # web browser on other platforms.
    webbrowser.open(path.as_uri())


class _AboutDialogContent(ttk.Frame):

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        big_label = ttk.Label(self, font=('', 16, ()), text="About Porcupine")
        big_label.pack(pady=5)

        self._textwidget = utils.create_passive_text_widget(
            self, width=60, height=18)
        self._textwidget.pack(fill='both', expand=True, padx=5, pady=5)

        # http://effbot.org/zone/tkinter-text-hyperlink.htm
        # that tutorial is almost as old as i am, but it's still usable
        self._textwidget.tag_config('link', foreground='blue', underline=True)
        self._textwidget.tag_bind('link', '<Enter>', self._enter_link)
        self._textwidget.tag_bind('link', '<Leave>', self._leave_link)
        self._link_tag_names = map('link-{}'.format, itertools.count())

        self._textwidget['state'] = 'normal'
        for text_chunk in _BORING_TEXT.strip().split('\n\n'):
            self._add_minimal_markdown(text_chunk)
        self._textwidget['state'] = 'disabled'

        label = ttk.Label(self, image=images.get('logo-200x200'),
                          cursor='hand2')
        label.pack(anchor='e')
        utils.set_tooltip(label, "Click to view in full size")
        label.bind('<Button-1>', show_huge_logo)

    def _add_minimal_markdown(self, text: str) -> None:
        parts: List[Union[str, Match[str]]] = []

        previous_end = 0
        for link in re.finditer(r'\[(.+?)\]\((.+?)\)', text):
            parts.append(text[previous_end:link.start()])
            parts.append(link)
            previous_end = link.end()
        parts.append(text[previous_end:])

        if self._textwidget.index('end - 1 char') != '1.0':
            # not the first time something is inserted
            self._textwidget.insert('end', '\n\n')

        for part in parts:
            if isinstance(part, str):
                self._textwidget.insert('end', part)
            else:
                # a link
                text, href = part.groups()
                tag = next(self._link_tag_names)
                self._textwidget.tag_bind(
                    tag, '<Button-1>',
                    functools.partial(self._open_link, href))
                self._textwidget.insert('end', text, ['link', tag])

    def _enter_link(self, junk_event: tkinter.Event) -> None:
        self._textwidget['cursor'] = 'hand2'

    def _leave_link(self, junk_event: tkinter.Event) -> None:
        self._textwidget['cursor'] = ''

    def _open_link(self, href: str, junk_event: tkinter.Event) -> None:
        webbrowser.open(href)


def show_about_dialog() -> None:
    dialog = tkinter.Toplevel()
    content = _AboutDialogContent(dialog)
    content.pack(fill='both', expand=True)

    content.update()       # make sure that the winfo stuff works
    dialog.minsize(content.winfo_reqwidth(), content.winfo_reqheight())
    dialog.title("About Porcupine")
    dialog.transient(get_main_window())
    dialog.wait_window()


def setup() -> None:
    actions.add_command("Help/About Porcupine...", show_about_dialog)
