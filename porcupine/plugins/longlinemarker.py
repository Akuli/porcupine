"""Maximum line length marker for Tkinter's text widget."""

import tkinter as tk
import tkinter.font as tkfont

import pygments.styles
import pygments.token

from porcupine import tabs, utils
from porcupine.settings import config


class LongLineMarker:

    def __init__(self, filetab):
        self.tab = filetab
        self.frame = tk.Frame(filetab.textwidget, width=1)
        self._height = 0        # on_configure() will run later

    def __enter__(self):
        config.connect('Font', 'family', self.do_update)
        config.connect('Font', 'size', self.do_update)
        config.connect('Editing', 'pygments_style',
                       self.on_style_changed, run_now=True)
        self.tab.filetype_changed_hook.connect(self.do_update)
        self.do_update()

    def __exit__(self, *error):
        config.disconnect('Font', 'family', self.do_update)
        config.disconnect('Font', 'size', self.do_update)
        config.disconnect('Editing', 'pygments_style', self.on_style_changed)
        self.tab.filetype_changed_hook.disconnect(self.do_update)

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

    # bind <Configure> to this
    def on_configure(self, event):
        self._height = event.height
        self.do_update()


def tab_callback(tab):
    if isinstance(tab, tabs.FileTab):
        marker = LongLineMarker(tab)
        with utils.temporary_bind(tab.textwidget, '<Configure>',
                                  marker.on_configure):
            with marker:
                yield
    else:
        yield


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)
