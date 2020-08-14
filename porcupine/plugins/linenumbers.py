"""Line numbers on left side of the file being edited."""

import tkinter.font
from typing import Optional

from porcupine import get_tab_manager, tabs, textwidget, utils


class LineNumbers:

    def __init__(self, parent: tkinter.Misc, textwidget_of_tab: tkinter.Text) -> None:
        self.textwidget = textwidget_of_tab
        self.canvas = tkinter.Canvas(parent, width=40)
        textwidget.use_pygments_theme(self.canvas, self._set_colors)

        # from options(3tk): "... the widget will generate a Tcl command by
        # concatenating the scroll command and two numbers."
        #
        # So if yscrollcommand is like this
        #
        #   bla bla bla
        #
        # it would be called like this
        #
        #   bla bla bla 0.123 0.456
        #
        # and by putting something in front on separate line we can make it get called like this
        #
        #   _do_update
        #   bla bla bla 0.123 0.456
        old_tcl_code = textwidget_of_tab['yscrollcommand']
        assert old_tcl_code
        new_tcl_code = self.canvas.register(self._do_update) + '\n' + old_tcl_code
        textwidget_of_tab['yscrollcommand'] = new_tcl_code

        textwidget_of_tab.bind('<<ContentChanged>>', self._do_update, add=True)
        self._do_update()

        self.canvas.bind('<<SettingChanged:font_family>>', self._update_canvas_width, add=True)
        self.canvas.bind('<<SettingChanged:font_size>>', self._update_canvas_width, add=True)
        self._update_canvas_width()

        self._clicked_place: Optional[str] = None
        self.canvas.bind('<Button-1>', self._on_click, add=True)
        self.canvas.bind('<ButtonRelease-1>', self._on_unclick, add=True)
        self.canvas.bind('<Double-Button-1>', self._on_double_click, add=True)
        self.canvas.bind('<Button1-Motion>', self._on_drag, add=True)

    def _set_colors(self, fg: str, bg: str) -> None:
        self.canvas['background'] = bg
        self._text_color = fg
        self.canvas.itemconfig('all', fill=fg)

    def _do_update(self, junk: object = None) -> None:
        self.canvas.delete('all')

        first_line = int(self.textwidget.index('@0,0').split('.')[0])
        last_line = int(self.textwidget.index(f'@0,{self.textwidget.winfo_height()}').split('.')[0])
        for lineno in range(first_line, last_line + 1):
            bbox = self.textwidget.bbox(f'{lineno}.0')
            if bbox is None:
                # line not showing up for whatever reason
                continue

            x, y, width, height = bbox
            self.canvas.create_text(0, y, text=f' {lineno}', anchor='nw', font='TkFixedFont', fill=self._text_color)

    def _update_canvas_width(self, junk: object = None) -> None:
        self.canvas['width'] = tkinter.font.Font(name='TkFixedFont', exists=True).measure('a' * 5)

    def _on_click(self, event: tkinter.Event) -> None:
        # go to clicked line
        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.mark_set('insert', f'@0,{event.y}')
        self._clicked_place = self.textwidget.index('insert')

    def _on_unclick(self, event: tkinter.Event) -> None:
        self._clicked_place = None

    def _on_double_click(self, event: tkinter.Event) -> None:
        # select the line the cursor is on, including trailing newline
        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.tag_add('sel', 'insert', 'insert + 1 line')

    def _on_drag(self, event: tkinter.Event) -> None:
        if self._clicked_place is None:
            # the user pressed down the mouse button and then moved the
            # mouse over the line numbers
            return

        # select multiple lines
        self.textwidget.mark_set('insert', f'@0,{event.y}')
        start = 'insert'
        end = self._clicked_place
        if self.textwidget.compare(start, '>', end):
            start, end = end, start

        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.tag_add('sel', start, end)


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        linenumbers = LineNumbers(tab.left_frame, tab.textwidget)
        linenumbers.canvas.pack(side='left', fill='y')


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
