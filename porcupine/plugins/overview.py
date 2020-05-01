"""High-level overview of the file being edited with small font."""

from porcupine import get_tab_manager, settings, tabs, utils
from porcupine.textwidget import ThemedText

GENERAL = settings.get_section('General')


def count_lines(textwidget):
    return int(textwidget.index('end - 1 char').split('.')[0])


class Overview:

    def __init__(self, tab):
        self._tab = tab

        self.widget = ThemedText(
            tab.right_frame, inactiveselectbackground='', takefocus=False)
        self.widget.pack(fill='y', expand=True)
        self.widget.tag_config('shown', background='#ccc')
        self.widget.tag_config('sel', background='')

        self.widget.insert('end', tab.textwidget.get('1.0', 'end - 1 char'))
        self.widget['state'] = 'disabled'   # after insert

        # When there are only a few lines of text in tab.textwidget, they don't
        # fill all of self._tab.textwidget vertically, but self.widget must
        # still add the 'shown' tag to the area that would be filled by it.
        # When this happens, some "fake" newline characters are added to the
        # end of self.widget and then those are tagged with 'shown'.
        self._how_many_fake_newlines = 0

        tab.textwidget['yscrollcommand'] = (
            tab.register(self._draw_selected_part) +
            '\n' + self._tab.textwidget['yscrollcommand'])
        self._draw_selected_part()

        self.widget.bind('<Button-1>', self._scroll)
        self.widget.bind('<Button1-Motion>', self._scroll)

    def set_font(self, junk_value=None):
        self.widget['font'] = (
            GENERAL['font_family'], int(GENERAL['font_size'] / 3), '')

    def on_content_changed(self, event):
        self.widget['state'] = 'normal'
        for change in event.data_json():
            self.widget.replace(
                change['start'], change['end'], change['new_text'])
        self.widget['state'] = 'disabled'

        self._draw_selected_part()

    def _set_number_of_fake_newlines(self, n):
        print('aaaaaaaaa', n)
        if n < 0:
            n = 0

        if n > self._how_many_fake_newlines:
            self.widget['state'] = 'normal'
            self.widget.insert(
                'end', '\n' * (n - self._how_many_fake_newlines))
            self.widget['state'] = 'disabled'
        elif n < self._how_many_fake_newlines:
            self.widget['state'] = 'normal'
            bye = self.widget.get(
                'end - 1 char - %d lines' % (self._how_many_fake_newlines - n),
                'end - 1 char')
            assert set(bye) == {'\n'}
            self.widget.delete(
                'end - 1 char - %d lines' % (self._how_many_fake_newlines - n),
                'end - 1 char')
            self.widget['state'] = 'disabled'

        self._how_many_fake_newlines = n

    def _draw_selected_part(self):
        relative_start, relative_end = self._tab.textwidget.yview()

        # tkinter doesn't provide a way to look up font metrics without
        # creating a stupid font object
        how_tall_are_lines = self._tab.tk.call(
            'font', 'metrics', self._tab.textwidget['font'], '-linespace')
        how_many_lines_fit_on_screen_at_once = int(
            self._tab.textwidget.winfo_height() / how_tall_are_lines)

        lines_in_file = count_lines(self._tab.textwidget)

        # +1 because line numbering starts at 1 in tkinter. I don't know
        # whether round() is more suitable for this than floor or ceil, but
        # rounding seems to work.
        first_line = round(relative_start * lines_in_file) + 1
        last_line = max(
            round(relative_end * lines_in_file) + 1,
            first_line + how_many_lines_fit_on_screen_at_once)

        self._set_number_of_fake_newlines(
            how_many_lines_fit_on_screen_at_once - lines_in_file)
        self.widget.tag_remove('shown', '1.0', 'end')
        self.widget.tag_add('shown', '%d.0' % first_line, '%d.0' % last_line)

        self.widget.see('shown.first')
        self.widget.see('shown.last')

    def _scroll(self, event):
        self._tab.textwidget.see(self.widget.index('@0,' + str(event.y)))


def on_new_tab(event):
    tab = event.data_widget()
    if not isinstance(tab, tabs.FileTab):
        return

    overview = Overview(tab)

    GENERAL.connect('font_family', overview.set_font, run_now=False)
    GENERAL.connect('font_size', overview.set_font, run_now=False)
    overview.set_font()

    utils.bind_with_data(
        tab.textwidget, '<<ContentChanged>>', overview.on_content_changed,
        add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
