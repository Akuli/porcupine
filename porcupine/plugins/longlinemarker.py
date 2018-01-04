"""Maximum line length marker for Tkinter's text widget."""

import tkinter
import tkinter.font as tkfont

import pygments.styles
import pygments.token

from porcupine import get_tab_manager, settings, tabs, utils

config = settings.get_section('General')


class LongLineMarker:

    def __init__(self, filetab):
        self.tab = filetab

        # this must not be a ttk frame because the background color
        # comes from the pygments style, not from the ttk theme
        self.frame = tkinter.Frame(filetab.textwidget, width=1)
        self._height = 0        # on_configure() will run later

    def setup(self):
        config.connect('font_family', self.do_update)
        config.connect('font_size', self.do_update)
        config.connect('pygments_style', self.on_style_changed, run_now=True)
        self.tab.textwidget.bind('<Configure>', self.on_configure, add=True)
        self.tab.bind('<<FiletypeChanged>>', self.do_update, add=True)
        self.tab.bind('<Destroy>', self.on_destroy, add=True)
        self.do_update()

    def on_destroy(self, event):
        config.disconnect('font_family', self.do_update)
        config.disconnect('font_size', self.do_update)
        config.disconnect('pygments_style', self.on_style_changed)

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
    if isinstance(event.data_widget, tabs.FileTab):
        LongLineMarker(event.data_widget).setup()


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
