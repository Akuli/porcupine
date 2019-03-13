import functools
import itertools
import os
import re
from urllib.request import pathname2url
import webbrowser

import teek as tk

from porcupine import actions, dirs, get_main_window, images
from porcupine import __version__ as porcupine_version


_BORING_TEXT = """
This is porcupine {version}.

Porcupine is a simple but powerful and configurable text editor written in \
Python using my [pythotk](https://github.com/Akuli/pythotk) library. It \
started as a proof-of-concept of a somewhat good editor written in tkinter, \
but it became a tool that I used every day at work. Later I created pythotk \
and ported porcupine to use that instead, because pythotk is much nicer to \
work with than tkinter.

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


def show_huge_logo():
    path = os.path.join(dirs.installdir, 'images', 'logo.gif')
    assert os.path.isfile(path)

    # web browsers are good at displaying large images, and webbrowser.open
    # actually tries xdg-open first, so this will be used on linux if an image
    # viewer program is installed, and i guess that other platforms just open
    # up a web browser or something
    webbrowser.open('file://' + pathname2url(path))


# unlike webbrowser.open, this returns None
def open_url(url):
    webbrowser.open(url)


class _AboutDialogContent(tk.Frame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        big_label = tk.Label(self, font=('', 16, ''), text="About Porcupine")
        big_label.pack(pady=5)

        # pythotk doesn't have a ttk::style api yet
        # this doesn't update when the user changes the ttk theme
        # but who would open the about dialog and then change theme?
        # makes no sense
        ttk_fg = tk.tcl_eval(
            tk.Color, 'ttk::style lookup TLabel.label -foreground')
        ttk_bg = tk.tcl_eval(
            tk.Color, 'ttk::style lookup TLabel.label -background')

        self._textwidget = tk.Text(
            self, width=60, height=18, font='TkDefaultFont',
            wrap='word', borderwidth=0, relief='flat',
            foreground=ttk_fg, background=ttk_bg, highlightbackground=ttk_bg)
        self._textwidget.pack(fill='both', expand=True, padx=5, pady=5)

        # http://effbot.org/zone/tkinter-text-hyperlink.htm
        # that tutorial is almost as old as i am, but it's still usable
        link = self._textwidget.get_tag('link')
        link['foreground'] = 'blue'
        link['underline'] = True
        link.bind('<Enter>', self._enter_link)
        link.bind('<Leave>', self._leave_link)

        self._link_tags = (self._textwidget.get_tag('link-' + str(number))
                           for number in itertools.count())

        for text_chunk in _BORING_TEXT.strip().split('\n\n'):
            self._add_minimal_markdown(text_chunk)

        # don't allow the user to write more text
        self._textwidget.config['state'] = 'disabled'

        label = tk.Label(self, image=images.get('logo-200x200'),
                         cursor='hand2')
        label.pack(anchor='e')
        tk.extras.set_tooltip(label, "Click to view in full size")
        label.bind('<Button-1>', show_huge_logo)

    def _add_minimal_markdown(self, text):
        parts = []   # contains strings and link regex matches

        previous_end = 0
        for link in re.finditer(r'\[(.+?)\]\((.+?)\)', text):
            parts.append(text[previous_end:link.start()])
            parts.append(link)
            previous_end = link.end()
        parts.append(text[previous_end:])

        if self._textwidget.start != self._textwidget.end:
            self._textwidget.insert(self._textwidget.end, '\n\n')

        for part in parts:
            if isinstance(part, str):
                self._textwidget.insert(self._textwidget.end, part)
            else:
                # a link
                text, href = part.groups()
                tag = next(self._link_tags)
                tag.bind('<Button-1>', functools.partial(open_url, href))
                self._textwidget.insert(
                    self._textwidget.end, text,
                    [self._textwidget.get_tag('link'), tag])

    def _enter_link(self):
        self._textwidget.config['cursor'] = 'hand2'

    def _leave_link(self):
        self._textwidget.config['cursor'] = ''


def show_about_dialog():
    dialog = tk.Window("About Porcupine")
    dialog.transient = get_main_window()

    content = _AboutDialogContent(dialog)
    content.pack(fill='both', expand=True)

    tk.update()       # make sure that the winfo stuff works
    # TODO: add to pythotk:
    #   * winfo reqwidth
    #   * winfo reqheight
    #   * wm minsize
    tk.tcl_eval(None, '''
    wm minsize %s [winfo reqwidth %s] [winfo reqheight %s]
    ''' % (dialog.toplevel.to_tcl(), content.to_tcl(), content.to_tcl()))

    dialog.wait_window()


def setup():
    actions.add_command("Help/About Porcupine...", show_about_dialog)
