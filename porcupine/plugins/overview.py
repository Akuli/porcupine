"""High-level overview of the file being edited with small font."""

import sys
import tkinter
from typing import Tuple

from porcupine import get_tab_manager, settings, tabs, textwidget, utils


LINE_THICKNESS = 1


def count_lines(textwidget: tkinter.Text) -> int:
    return int(textwidget.index('end - 1 char').split('.')[0])


# We want self to have the same text content and colors as the main
# text. We do this efficiently with a peer widget.
#
# The only way to bold text is to specify a tag with a bold font, and that's
# what the main text widget does. The peer text widget then gets the same tag
# with the same font, including the same font size. There's is a way to specify
# a font so that you only tell it to bold and nothing more, but then it just
# chooses a default size that is not widget-specific. This means that we need
# a way to override the font of a tag (it doesn't matter if we don't get bolded
# text in the overview). The only way to override a font is to use another tag
# that has a higher priority.
#
# There is only one tag that is not common to both widgets, sel. It represents
# the text being selected, and we abuse it for setting the smaller font size.
# This means that all of the text has to be selected all the time.
class Overview(tkinter.Text):

    def __init__(self, master: tkinter.BaseWidget, tab: tabs.FileTab) -> None:
        super().__init__(master)
        textwidget.create_peer_widget(tab.textwidget, self)
        self['width'] = 25
        self['exportselection'] = False
        self['takefocus'] = False
        self['yscrollcommand'] = self._update_vast
        self['wrap'] = 'none'

        self._tab = tab
        self._tab.textwidget['highlightthickness'] = LINE_THICKNESS

        self.tag_config('sel', foreground='', background='')

        # To indicate the area visible in tab.textwidget, we can't use a tag,
        # because tag configuration is the same for both widgets (except for
        # one tag that we are already abusing). Instead, we put a bunch of
        # frames on top of the text widget to make up a border. I call this
        # "vast" for "visible area showing thingies".
        self._vast = [
            tkinter.Frame(self),
            tkinter.Frame(self),
            tkinter.Frame(self),
            tkinter.Frame(self),
        ]

        tab.textwidget['yscrollcommand'] = (
            tab.register(self._scroll_callback) +
            '\n' + self._tab.textwidget['yscrollcommand'])

        self.bind('<Button-1>', self._on_click_and_drag, add=True)
        self.bind('<Button1-Motion>', self._on_click_and_drag, add=True)

        # We want to prevent the user from selecting anything in self, because
        # of abusing the 'sel' tag. Binding <Button-1> and <Button1-Motion>
        # isn't quite enough.
        self.bind('<Button1-Enter>', self._on_click_and_drag, add=True)
        self.bind('<Button1-Leave>', self._on_click_and_drag, add=True)

        # TODO: can this line be deleted safely?
        self.bind('<Configure>', self._update_vast, add=True)

        self.bind('<<SettingChanged:font_family>>', self.set_font, add=True)
        self.bind('<<SettingChanged:font_size>>', self.set_font, add=True)
        self.set_font()
        tab.bind('<<FiletypeChanged>>', self.set_font, add=True)

        # don't know why after_idle doesn't work. Adding a timeout causes
        # issues with tests.
        if 'pytest' not in sys.modules:
            self.after(50, self._scroll_callback)

    def set_colors(self, foreground: str, background: str) -> None:
        self['foreground'] = foreground
        self['background'] = background
        self['inactiveselectbackground'] = background   # must be non-empty?

        self._tab.textwidget['highlightcolor'] = foreground
        for frame in self._vast:
            frame['background'] = foreground

    def set_font(self, junk: object = None) -> None:
        font = (
            settings.get('font_family', str),
            round(settings.get('font_size', int) / 3),
            ())
        how_to_show_tab = ' ' * self._tab.filetype.indent_size

        # tkinter doesn't provide a better way to do font stuff than stupid
        # font object
        self['tabs'] = self.tk.call('font', 'measure', font, how_to_show_tab)
        self.tag_config('sel', font=font)
        self._update_vast()

    def _scroll_callback(self) -> None:
        first_visible_index = self._tab.textwidget.index('@0,0')
        last_visible_index = self._tab.textwidget.index('@0,10000000')
        self.see(first_visible_index)
        self.see(last_visible_index)
        self._update_vast()

    def _do_math(self) -> Tuple[float, float, float, float, int, float, int]:
        # FIXME: this is a little bit off in very long files

        # tkinter doesn't provide a better way to look up font metrics without
        # creating a stupid font object
        how_tall_are_lines_on_editor: int = self._tab.tk.call(
            'font', 'metrics', self._tab.textwidget['font'], '-linespace')
        how_tall_are_lines_overview: int = self._tab.tk.call(
            'font', 'metrics', self.tag_cget('sel', 'font'), '-linespace')

        (overview_scroll_relative_start,
         overview_scroll_relative_end) = self.yview()
        (text_scroll_relative_start,
         text_scroll_relative_end) = self._tab.textwidget.yview()

        how_many_lines_total = count_lines(self._tab.textwidget)
        how_many_lines_fit_on_editor = (
            self._tab.textwidget.winfo_height() / how_tall_are_lines_on_editor)

        total_height = how_many_lines_total * how_tall_are_lines_overview

        return (overview_scroll_relative_start,
                overview_scroll_relative_end,
                text_scroll_relative_start,
                text_scroll_relative_end,
                how_many_lines_total,
                how_many_lines_fit_on_editor,
                total_height)

    def _update_vast(self, *junk: object) -> None:
        if not self.tag_cget('sel', 'font'):
            # view was created just a moment ago, set_font() hasn't ran yet
            return

        (overview_scroll_relative_start,
         overview_scroll_relative_end,
         text_scroll_relative_start,
         text_scroll_relative_end,
         how_many_lines_total,
         how_many_lines_fit_on_editor,
         total_height) = self._do_math()

        if (text_scroll_relative_start == 0.0
                and text_scroll_relative_end == 1.0):
            # it fits fully on screen, make text_scroll_relative_end correspond
            # to the end of what is actually visible (beyond end of file)
            text_scroll_relative_end = (
                how_many_lines_fit_on_editor / how_many_lines_total)

        vast_top = (text_scroll_relative_start
                    - overview_scroll_relative_start) * total_height
        vast_bottom = (text_scroll_relative_end
                       - overview_scroll_relative_start) * total_height
        vast_height = (text_scroll_relative_end
                       - text_scroll_relative_start) * total_height

        # no idea why 5
        width = self.winfo_width() - 5

        self._vast[0].place(
            x=0, y=vast_top, width=width, height=LINE_THICKNESS)
        self._vast[1].place(
            x=0, y=vast_top, width=LINE_THICKNESS, height=vast_height)
        self._vast[2].place(
            x=0, y=(vast_bottom - LINE_THICKNESS),
            width=width, height=LINE_THICKNESS)
        self._vast[3].place(
            x=(width - LINE_THICKNESS), y=vast_top,
            width=LINE_THICKNESS, height=vast_height)

        self.tag_add('sel', '1.0', 'end')

    def _on_click_and_drag(self, event: tkinter.Event) -> utils.BreakOrNone:
        (overview_scroll_relative_start,
         overview_scroll_relative_end,
         text_scroll_relative_start,
         text_scroll_relative_end,
         how_many_lines_total,
         how_many_lines_fit_on_editor,
         total_height) = self._do_math()

        if (text_scroll_relative_start != 0.0
                or text_scroll_relative_end != 1.0):
            # file doesn't fit fully on screen, need to scroll
            text_showing_propotion = (
                text_scroll_relative_end - text_scroll_relative_start)
            middle_relative = (event.y/total_height
                               + overview_scroll_relative_start)
            start_relative = middle_relative - text_showing_propotion/2
            self._tab.textwidget.yview_moveto(start_relative)
            self._update_vast()

        return 'break'


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if not isinstance(tab, tabs.FileTab):
        return

    overview = Overview(tab.right_frame, tab)
    textwidget.use_pygments_theme(overview, overview.set_colors)
    overview.pack(fill='y', expand=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
