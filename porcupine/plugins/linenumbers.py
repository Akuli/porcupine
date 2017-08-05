"""Line numbers for tkinter's Text widget."""

import tkinter as tk

import porcupine
from porcupine import tabs
from porcupine.textwidget import ThemedText


class ScrollManager:
    """Scroll two text widgets with one scrollbar."""

    def __init__(self, scrollbar, main_widget, other_widgets):
        self._scrollbar = scrollbar
        self._main_widget = main_widget
        self._widgets = [main_widget] + other_widgets

    def enable(self):
        self._scrollbar['command'] = self._yview
        for widget in self._widgets:
            widget['yscrollcommand'] = self._set

    def _yview(self, *args):
        for widget in self._widgets:
            widget.yview(*args)

    def _set(self, beginning, end):
        self._scrollbar.set(beginning, end)
        for widget in self._widgets:
            widget.yview('moveto', beginning)


class LineNumbers(ThemedText):

    def __init__(self, parent, textwidget, **kwargs):
        super().__init__(parent, width=6, height=1, **kwargs)
        self.textwidget = textwidget
        self.insert('1.0', " 1")    # this is always there
        self['state'] = 'disabled'  # must be after the insert
        self._linecount = 1
        self.bind('<Button-1>', self._on_click)
        self.bind('<Double-Button-1>', self._on_double_click)
        self.bind('<Button1-Motion>', self._on_drag)

    def do_update(self):
        """This should be ran when the line count changes."""
        linecount = int(self.textwidget.index('end - 1 char').split('.')[0])
        if linecount > self._linecount:
            # add more linenumbers
            self['state'] = 'normal'
            for i in range(self._linecount + 1, linecount + 1):
                self.insert('end - 1 char', '\n %d' % i)
            self['state'] = 'disabled'
        if linecount < self._linecount:
            # delete the linenumbers we don't need
            self['state'] = 'normal'
            self.delete('%d.0 lineend' % linecount, 'end - 1 char')
            self['state'] = 'disabled'
        self._linecount = linecount

    def _on_click(self, event):
        # go to clicked line
        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.mark_set('insert', '@0,%d' % event.y)
        self._clicked_place = self.textwidget.index('insert')
        return 'break'

    def _on_double_click(self, event):
        # select the line the cursor is on, including trailing newline
        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.tag_add('sel', 'insert', 'insert + 1 line')
        return 'break'

    def _on_drag(self, event):
        # select multiple lines
        self.textwidget.mark_set('insert', '@0,%d' % event.y)
        start = 'insert'
        end = self._clicked_place
        if self.textwidget.compare(start, '>', end):
            start, end = end, start

        self.textwidget.tag_remove('sel', '1.0', 'end')
        self.textwidget.tag_add('sel', start, end)
        return 'break'


def on_new_tab(event):
    tab = event.widget.tabs[-1]
    if not isinstance(tab, tabs.FileTab):
        return

    linenumbers = LineNumbers(tab.mainframe, tab.textwidget)
    linenumbers.pack(side='left', fill='y')
    ScrollManager(tab.scrollbar, tab.textwidget, [linenumbers]).enable()
    tab.textwidget.modified_hook.connect(linenumbers.do_update)
    linenumbers.do_update()

    def on_destroy(event):
        # linenumbers will be destroyed automatically
        tab.textwidget.modified_hook.disconnect(linenumbers.do_update)

    tab.textwidget.bind('<Destroy>', on_destroy)


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)


if __name__ == '__main__':
    from porcupine.settings import config

    root = tk.Tk()
    config.load()

    text = ThemedText(root)
    linenumbers = LineNumbers(root, text)
    linenumbers.pack(side='left', fill='y')
    text.pack(side='left', fill='both', expand=True)

    def on_lineno_change(event):
        text.after_idle(linenumbers.do_update)

    # this isn't perfect but this is good enough for this test
    text.bind('<Return>', on_lineno_change)
    text.bind('<BackSpace>', on_lineno_change)
    text.bind('<Delete>', on_lineno_change)

    root.mainloop()
