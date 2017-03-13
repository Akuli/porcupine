import math
import tkinter as tk


class MultiScrollbar(tk.Scrollbar):
    """A scrollbar that scrolls multiple widgets.

    This widget assumes that each scrolled widget and this scrollbar
    will be packed next to each other, and all text widgets have the
    same number of lines in them.
    """

    def __init__(self, master, widgetlist, **kwargs):
        super().__init__(master, command=self._on_scrollbar, **kwargs)
        self._widgets = widgetlist
        for widget in widgetlist:
            widget['yscrollcommand'] = self._on_widget_scroll

    def _on_scrollbar(self, *args):
        for widget in self._widgets:
            widget.yview(*args)

    def _on_widget_scroll(self, beginning, end):
        self.set(beginning, end)
        self._on_scrollbar('moveto', beginning)


if __name__ == '__main__':
    # simple test
    root = tk.Tk()
    left = tk.Text(width=20)
    left.pack(side='left', fill='both', expand=True)
    right = tk.Text(width=20)
    right.pack(side='left', fill='both', expand=True)

    scrollbar = MultiScrollbar(root, [left, right])
    scrollbar.pack(side='right', fill='y')

    for i in range(1, 31):
        left.insert('end-1c', 'left %d\n' % i)
        right.insert('end-1c', 'right %d\n' % i)

    root.mainloop()
