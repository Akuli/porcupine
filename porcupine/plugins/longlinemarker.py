"""Maximum line length marker for Tkinter's text widget."""

import tkinter as tk
import tkinter.font as tkfont

import pygments.styles
import pygments.token

import porcupine
from porcupine import tabs
from porcupine.settings import config


class LongLineMarker:

    def __init__(self, filetab):
        self.tab = filetab
        self.frame = tk.Frame(filetab.textwidget, width=1)
        self._height = 0        # on_configure() will run later

    def setup(self):
        config.connect('Font', 'family', self.do_update)
        config.connect('Font', 'size', self.do_update)
        config.connect('Editing', 'pygments_style',
                       self.on_style_changed, run_now=True)
        self.tab.textwidget.bind('<Configure>', self.on_configure, add=True)
        self.tab.bind('<<FiletypeChanged>>', self.do_update, add=True)
        self.tab.bind('<Destroy>', self.on_destroy, add=True)
        self.do_update()

    def on_destroy(self, event):
        config.disconnect('Font', 'family', self.do_update)
        config.disconnect('Font', 'size', self.do_update)
        config.disconnect('Editing', 'pygments_style', self.on_style_changed)

    def do_update(self, junk=None):
        column = self.tab.filetype.max_line_length
        if column == 0:
            # maximum line length is disabled, see filetypes.ini docs
            return

        font = tkfont.Font(name=self.tab.textwidget['font'], exists=True)
        where = font.measure(' ' * self.tab.filetype.max_line_length)
        self.frame.place(x=where, height=self._height)

    def on_style_changed(self, name):
        # do the same thing as porcupine's color theme menu does
        infos = dict(iter(pygments.styles.get_style_by_name(name)))
        for tokentype in [pygments.token.Error, pygments.token.Name.Exception]:
            if tokentype in infos:
                for key in ['bgcolor', 'color', 'border']:
                    if infos[tokentype][key] is not None:
                        self.frame['bg'] = '#' + infos[tokentype][key]
                        return

        # stupid fallback
        self.frame['bg'] = 'red'

    def on_configure(self, event):
        self._height = event.height
        self.do_update()


def on_new_tab(event):
    new_tab = event.widget.tabs[-1]
    if isinstance(new_tab, tabs.FileTab):
        marker = LongLineMarker(new_tab)
        marker.setup()


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)
