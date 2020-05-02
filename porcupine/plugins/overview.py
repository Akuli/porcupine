"""High-level overview of the file being edited with small font."""

import sys
import tkinter

from porcupine import get_tab_manager, settings, tabs, utils
from porcupine.textwidget import ThemedText

GENERAL = settings.get_section('General')


def count_lines(textwidget):
    return int(textwidget.index('end - 1 char').split('.')[0])


# We want self to have the same text content and colors as the main
# text. We do this efficiently with a peer widget. See "PEER WIDGETS" in
# text(3tk) for more.
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
class Overview(ThemedText):

    def __init__(self, master, tab):
        # ThemedText.__init__ calls set_colors() which needs _vast
        self._vast = []

        super().__init__(master, width=25, exportselection=False,
                         takefocus=False, create_peer_from=tab.textwidget,
                         yscrollcommand=self._update_vast)
        self._tab = tab
        self.tag_config('sel', foreground='', background='')

        # To indicate the area visible in tab.textwidget, we can't use a tag,
        # because tag configuration is the same for both widgets (except for
        # one tag that we are already abusing). Instead, we put a bunch of
        # frames on top of the text widget to make up a border. I call this
        # "vast" for "visible area showing thingies".
        self._vast.extend(tkinter.Frame(self) for lel in range(4))
        self.set_colors(*self._colors)

        self._got_focus = True

        tab.textwidget['yscrollcommand'] = (
            tab.register(self._scroll_callback) +
            '\n' + self._tab.textwidget['yscrollcommand'])

        self.bind('<Button-1>', self._on_click_and_drag)
        self.bind('<Button1-Motion>', self._on_click_and_drag)

        forward_list = [
            # TODO: forward scrolling correctly on other platforms than linux
            '<Button-1>', '<Button1-Motion>',       # clicking and dragging
            '<Button-4>', '<Button-5>',             # mouse wheel
        ]
        for event_name in forward_list:
            for frame in self._vast:
                utils.forward_event(event_name, frame, self)

        # We want to prevent the user from selecting anything in self, because
        # of abusing the 'sel' tag. Binding <Button-1> and <Button1-Motion>
        # isn't quite enough.
        self.bind('<Button1-Enter>', self._on_click_and_drag)
        self.bind('<Button1-Leave>', self._on_click_and_drag)

        self._temporary_binds = [
            utils.temporary_bind(
                self.winfo_toplevel(), '<FocusIn>', self._on_focus_in),
            utils.temporary_bind(
                self.winfo_toplevel(), '<FocusOut>', self._on_focus_out),
            utils.temporary_bind(
                self.winfo_toplevel(), '<Configure>', self._update_vast),
            utils.temporary_bind(
                tab.master, '<<NotebookTabChanged>>', self._update_vast),
        ]
        for binding in self._temporary_binds:
            binding.__enter__()
        tab.bind('<Destroy>', self._clean_up, add=True)

        GENERAL.connect('font_family', self.set_font, run_now=False)
        GENERAL.connect('font_size', self.set_font, run_now=False)
        self.set_font()

        # don't know why after_idle doesn't work. Adding a timeout causes
        # issues with tests.
        if 'pytest' not in sys.modules:
            self.after(50, self._scroll_callback)

    def _clean_up(self, junk_event):
        for binding in self._temporary_binds:
            binding.__exit__(None, None, None)

        GENERAL.disconnect('font_family', self.set_font)
        GENERAL.disconnect('font_size', self.set_font)

    # this overrides ThemedText.set_colors
    def set_colors(self, foreground, background):
        self._colors = (foreground, background)
        self['foreground'] = foreground
        self['background'] = background
        self['inactiveselectbackground'] = background   # must be non-empty?

        for frame in self._vast:
            frame['background'] = utils.mix_colors(foreground, background)

    def set_font(self, junk_value=None):
        self.tag_config('sel', font=(
            GENERAL['font_family'], round(GENERAL['font_size'] / 3), ''))
        self._update_vast()

    def _scroll_callback(self):
        first_visible_index = self._tab.textwidget.index('@0,0')
        last_visible_index = self._tab.textwidget.index('@0,10000000')
        self.see(first_visible_index)
        self.see(last_visible_index)
        self._update_vast()

    def _do_math(self):
        # FIXME: this is a little bit off in very long files

        # tkinter doesn't provide a better way to look up font metrics without
        # creating a stupid font object
        how_tall_are_lines_on_editor = self._tab.tk.call(
            'font', 'metrics', self._tab.textwidget['font'], '-linespace')
        how_tall_are_lines_overview = self._tab.tk.call(
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

    def _update_vast(self, *junk):
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

        # no idea why 6
        width = self.winfo_width() - 6

        size = 3
        self._vast[0].place(
            x=0, y=vast_top, width=width, height=size)
        self._vast[1].place(
            x=0, y=vast_top, width=size, height=vast_height)
        self._vast[2].place(
            x=0, y=(vast_bottom - size), width=width, height=size)
        self._vast[3].place(
            x=(width - size), y=vast_top, width=size, height=vast_height)

        self.tag_add('sel', '1.0', 'end')

    def _on_click_and_drag(self, event):
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

    def _on_focus_in(self, event):
        if event.widget is event.widget.winfo_toplevel():
            self._got_focus = True
            self._update_vast()

    def _on_focus_out(self, event):
        if event.widget is event.widget.winfo_toplevel():
            self._got_focus = False
            self._update_vast()


def on_new_tab(event):
    tab = event.data_widget()
    if not isinstance(tab, tabs.FileTab):
        return

    overview = Overview(tab.right_frame, tab)
    overview.pack(fill='y', expand=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
