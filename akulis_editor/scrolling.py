import math
import tkinter as tk


class MultiScrollbar(tk.Scrollbar):
    """A scrollbar that scrolls multiple widgets.

    The scrollbar also has an on_visibility_changed callback list. The
    callbacks will be called like callback(first_lineno, last_lineno)
    when the widgets are scrolled.

    This widget assumes that each scrolled widget and this scrollbar
    will be packed next to each other, and all text widgets have the
    same number of lines in them.
    """

    def __init__(self, master, widgetlist, **kwargs):
        super().__init__(master, command=self._on_scrollbar, **kwargs)
        self._widgets = widgetlist
        self._visibility = (1, 1)
        self.on_visibility_changed = []
        for widget in widgetlist:
            widget['yscrollcommand'] = self._on_widget_scroll
        self._widgets[0].bind('<<Configure>>', self._do_visibility_changed)

    def _do_visibility_changed(self, event=None):
        linecount = int(self._widgets[0].index('end-1c').split('.')[0])
        start, end = self.get()
        start = math.floor(start * linecount)
        end = math.ceil(end * linecount)

        if start < 1:
            start = 1
        if end > linecount:
            end = linecount

        if self._visibility != (start, end):
            self._visibility = (start, end)
            for callback in self.on_visibility_changed:
                callback(start, end)

    def _on_scrollbar(self, *args):
        for widget in self._widgets:
            widget.yview(*args)
        self._do_visibility_changed()

    def _on_widget_scroll(self, beginning, end):
        self.set(beginning, end)
        self._on_scrollbar('moveto', beginning)
        self._do_visibility_changed()


if __name__ == '__main__':
    # simple test
    root = tk.Tk()
    left = tk.Text(width=20)
    left.pack(side='left', fill='both', expand=True)
    right = tk.Text(width=20)
    right.pack(side='left', fill='both', expand=True)
    scrollbar = MultiScrollbar(root, [left, right])
    scrollbar.pack(side='right', fill='y')
    scrollbar.on_visibility_changed.append(print)
    left.insert('1.0', '\n'.join(map('left {}'.format, range(1, 31))))
    right.insert('1.0', '\n'.join(map('left {}'.format, range(1, 31))))
    root.mainloop()
