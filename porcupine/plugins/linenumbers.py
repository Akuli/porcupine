"""Line numbers for text widget."""

from porcupine import get_tab_manager, tabs, utils
from porcupine.textwidget import ThemedText


class LineNumbers(ThemedText):

    def __init__(self, parent, textwidget: ThemedText, **kwargs):
        super().__init__(parent, width=6, height=1, **kwargs)
        self.textwidget = textwidget
        self.insert(self.start, " 1")    # this is always there
        self.config['state'] = 'disabled'  # must be after the insert
        self._linecount = 1

        self._clicked_place = None
        self.bind('<Button-1>', self._on_click, event=True)
        self.bind('<ButtonRelease-1>', self._on_unclick)
        self.bind('<Double-Button-1>', self._on_double_click)
        self.bind('<Button1-Motion>', self._on_drag, event=True)

    def do_update(self):
        """This should be ran when the line count changes."""
        linecount = self.textwidget.end.line
        if linecount > self._linecount:
            # add more linenumbers
            self.config['state'] = 'normal'
            for i in range(self._linecount + 1, linecount + 1):
                self.insert(self.end, '\n %d' % i)
            self.config['state'] = 'disabled'
        if linecount < self._linecount:
            # delete the linenumbers we don't need
            self.config['state'] = 'normal'
            self.delete(self.TextIndex(linecount, 0).lineend(), self.end)
            self.config['state'] = 'disabled'
        self._linecount = linecount

    def _on_click(self, event):
        # go to clicked line
        self.textwidget.get_tag('sel').remove()
        # TODO: add @ support to pythotk
        cursor_pos = tk.tcl_call(self.textwidget.TextIndex, self.textwidget,
                                 'index', '@0,%d' % event.y)
        self._clicked_place = self.textwidget.marks['insert'] = cursor_pos
        return 'break'

    def _on_unclick(self):
        self._clicked_place = None

    def _on_double_click(self, event):
        # select the line the cursor is on, including trailing newline
        cursor = self.textwidget.marks['insert']
        self.textwidget.get_tag('sel').remove()
        self.textwidget.get_tag('sel').add(cursor, cursor.forward(lines=1))
        return 'break'

    def _on_drag(self, event):
        if self._clicked_place is None:
            # the user pressed down the mouse button and then moved the
            # mouse over the line numbers
            return 'break'

        # select multiple lines
        # TODO: add @ support to pythotk
        cursor_pos = tk.tcl_call(self.textwidget.TextIndex, self.textwidget,
                                 'index', '@0,%d' % event.y)
        self.textwidget.marks['insert'] = cursor_pos

        start = min(cursor_pos, self._clicked_place)
        end = max(cursor_pos, self._clicked_place)
        self.textwidget.get_tag('sel').remove()
        self.textwidget.get_tag('sel').add(start, end)
        return 'break'


def _setup_scrolling(main_text, other_text):
    # do nothing when mouse is wheeled on other_text
    other_text.config['yscrollcommand'].connect(
        lambda start, end: other_text.yview('moveto', main_text.yview()[0]))

    # also scroll other_text when main_text's scrolling position changes
    main_text.config['yscrollcommand'].connect(
        lambda start, end: other_text.yview('moveto', start))


def on_new_tab(tab):
    if not isinstance(tab, tabs.FileTab):
        return

    linenumbers = LineNumbers(tab.left_frame, tab.textwidget)
    linenumbers.pack(side='left', fill='y')
    _setup_scrolling(tab.textwidget, linenumbers)
    tab.textwidget.bind('<<ContentChanged>>', linenumbers.do_update)
    linenumbers.do_update()


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
