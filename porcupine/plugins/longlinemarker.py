"""Maximum line length marker for Tkinter's text widget."""

import tkinter
import tkinter.font as tkfont

import pygments.styles  # type: ignore
import pygments.token   # type: ignore

from porcupine import get_tab_manager, settings, tabs, utils


class LongLineMarker:

    def __init__(self, filetab: tabs.FileTab) -> None:
        self.tab = filetab

        # this must not be a ttk frame because the background color
        # comes from the pygments style, not from the ttk theme
        self.frame = tkinter.Frame(filetab.textwidget, width=1)
        self._height = 0        # on_configure() will run later

    def setup(self) -> None:
        self.tab.bind('<<SettingChanged:font_family>>', self.do_update, add=True)
        self.tab.bind('<<SettingChanged:font_size>>', self.do_update, add=True)
        self.tab.bind('<<SettingChanged:pygments_style>>', self.on_style_changed, add=True)
        self.tab.textwidget.bind('<Configure>', self.on_configure, add=True)

        self.do_update()
        self.on_style_changed()

    def do_update(self, junk: object = None) -> None:
        column = self.tab.filetype.max_line_length
        if column == 0:
            # maximum line length is disabled, see filetypes.ini docs
            return

        font = tkfont.Font(name=self.tab.textwidget['font'], exists=True)
        where = font.measure(' ' * self.tab.filetype.max_line_length)
        self.frame.place(x=where, height=self._height)

    def on_style_changed(self, junk: object = None) -> None:
        style = pygments.styles.get_style_by_name(settings.get('pygments_style', str))
        infos = dict(iter(style))   # iterating is documented
        for tokentype in [pygments.token.Error, pygments.token.Name.Exception]:
            if tokentype in infos:
                for key in ['bgcolor', 'color', 'border']:
                    if infos[tokentype][key] is not None:
                        self.frame['bg'] = '#' + infos[tokentype][key]
                        return

        # stupid fallback
        self.frame['bg'] = 'red'

    def on_configure(self, event: tkinter.Event) -> None:
        assert event.height != '??'
        self._height = event.height
        self.do_update()


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        LongLineMarker(tab).setup()


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
