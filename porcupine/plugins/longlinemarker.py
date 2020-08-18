"""Maximum line length marker."""

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
        self._width = self._height = 1        # on_configure() will run soon

    def setup(self) -> None:
        assert not self.tab.textwidget.cget('xscrollcommand')
        self.tab.textwidget.config(xscrollcommand=self.do_update)
        self.tab.bind('<<TabSettingChanged:max_line_length>>', self.do_update, add=True)
        self.tab.bind('<<SettingChanged:font_family>>', self.do_update, add=True)
        self.tab.bind('<<SettingChanged:font_size>>', self.do_update, add=True)
        self.tab.bind('<<SettingChanged:pygments_style>>', self.on_style_changed, add=True)
        self.tab.textwidget.bind('<Configure>', self.on_configure, add=True)

        self.do_update()
        self.on_style_changed()

    def do_update(self, *junk: object) -> None:
        max_line_length = self.tab.settings.get('max_line_length', int)
        if max_line_length <= 0:
            # marker is disabled
            self.frame.place_forget()
            return

        font = tkfont.Font(name=self.tab.textwidget.cget('font'), exists=True)
        marker_x = font.measure(' ' * max_line_length)

        # these are relative to the length of the longest line in the text widget
        scroll_start, scroll_end = self.tab.textwidget.xview()

        # we want relative to visible area width
        relative_scroll_start = scroll_start / (scroll_end - scroll_start)

        self.frame.place(
            relx=(marker_x/self._width - relative_scroll_start),
            height=self._height)

    def on_style_changed(self, junk: object = None) -> None:
        style = pygments.styles.get_style_by_name(settings.get('pygments_style', str))
        infos = dict(iter(style))   # iterating is documented
        for tokentype in [pygments.token.Error, pygments.token.Name.Exception]:
            if tokentype in infos:
                for key in ['bgcolor', 'color', 'border']:
                    if infos[tokentype][key] is not None:
                        self.frame.config(bg=('#' + infos[tokentype][key]))
                        return

        # stupid fallback
        self.frame.config(bg='red')

    def on_configure(self, event: tkinter.Event) -> None:
        # this way to calculate it is weird but seems to work
        bbox = self.tab.textwidget.bbox('@0,0')
        assert bbox is not None
        x, y, width, height = bbox
        weird_x_padding = 2*x
        weird_y_padding = weird_x_padding   # don't know better way, bbox y may be off screen

        self._width = event.width - weird_x_padding
        self._height = event.height - weird_y_padding
        self.do_update()


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        # raymond hettinger says 90-ish
        tab.settings.add_option('max_line_length', 90)
        LongLineMarker(tab).setup()


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
