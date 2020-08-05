"""Line numbers for tkinter's Text widget."""
# FIXME: sometimes line numbers are off in y direction. Hard to reproduce.

import tkinter
import typing

from porcupine import get_tab_manager, tabs, utils
from porcupine.textwidget import ThemedText


class LineNumbers(ThemedText):

    def __init__(
            self, parent: tkinter.BaseWidget, textwidget: tkinter.Text,
            **kwargs: typing.Any) -> None:
        super().__init__(parent, width=6, height=1, **kwargs)
        self.textwidget = textwidget
        self.insert('1.0', " 1")    # this is always there
        self['state'] = 'disabled'  # must be after the insert
        self._linecount = 1

        self._clicked_place: typing.Optional[str] = None
        self.bind('<Button-1>', self._on_click, add=True)
        self.bind('<ButtonRelease-1>', self._on_unclick, add=True)
        self.bind('<Double-Button-1>', self._on_double_click, add=True)
        self.bind('<Button1-Motion>', self._on_drag, add=True)

    def do_update(self, junk: typing.Any = None) -> None:
        """This should be ran when the line count changes."""
        linecount = int(self.textwidget.index('end - 1 char').split('.')[0])
        if linecount > self._linecount:
            # add more linenumbers
            self['state'] = 'normal'
            for i in range(self._linecount + 1, linecount + 1):
                self.insert('end - 1 char', f'\n {i}')
            self['state'] = 'disabled'
        if linecount < self._linecount:
            # delete the linenumbers we don't need
            self['state'] = 'normal'
            self.delete(f'{linecount}.0 lineend', 'end - 1 char')
            self['state'] = 'disabled'
        self._linecount = linecount

    def _on_click(self, event: tkinter.Event) -> utils.BreakOrNone:
        # go to clicked line
        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.mark_set('insert', f'@0,{event.y}')
        self._clicked_place = self.textwidget.index('insert')
        return 'break'

    def _on_unclick(self, event: tkinter.Event) -> None:
        self._clicked_place = None

    def _on_double_click(self, event: tkinter.Event) -> utils.BreakOrNone:
        # select the line the cursor is on, including trailing newline
        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.tag_add('sel', 'insert', 'insert + 1 line')
        return 'break'

    def _on_drag(self, event: tkinter.Event) -> utils.BreakOrNone:
        if self._clicked_place is None:
            # the user pressed down the mouse button and then moved the
            # mouse over the line numbers
            return 'break'

        # select multiple lines
        self.textwidget.mark_set('insert', f'@0,{event.y}')
        start = 'insert'
        end = self._clicked_place
        if self.textwidget.compare(start, '>', end):
            start, end = end, start

        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.tag_add('sel', start, end)
        return 'break'


def _setup_scrolling(main_text: tkinter.Text, other_text: tkinter.Text) -> None:
    # do nothing when mouse is wheeled on other_text
    other_text['yscrollcommand'] = lambda start, end: (
        other_text.yview_moveto(main_text.yview()[0]))

    old_command = main_text['yscrollcommand']
    assert isinstance(old_command, str)   # string of tcl code

    # also scroll other_text when main_text's scrolling position changes
    def new_yscrollcommand(start: str, end: str) -> None:
        # from options(3tk): "... the widget will generate a Tcl command by
        # concatenating the scroll command and two numbers."
        main_text.tk.eval(f'{old_command} {start} {end}')
        other_text.yview_moveto(float(start))

    main_text['yscrollcommand'] = new_yscrollcommand


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        linenumbers = LineNumbers(tab.left_frame, tab.textwidget)
        linenumbers.pack(side='left', fill='y')
        _setup_scrolling(tab.textwidget, linenumbers)
        tab.textwidget.bind('<<ContentChanged>>', linenumbers.do_update, add=True)
        linenumbers.do_update()


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)


if __name__ == '__main__':
    root = tkinter.Tk()

    text = ThemedText(root)
    text.pack(side='right', fill='both', expand=True)
    linenumbers = LineNumbers(root, text)
    linenumbers.pack(side='left', fill='y')

    def on_lineno_change(event: tkinter.Event) -> None:
        text.after_idle(linenumbers.do_update)

    # this isn't perfect but this is good enough for this test
    text.bind('<Return>', on_lineno_change)
    text.bind('<BackSpace>', on_lineno_change)
    text.bind('<Delete>', on_lineno_change)

    root.mainloop()
