"""A scrollbar that scrolls multiple widgets."""

import tkinter as tk


class MultiScrollbar(tk.Scrollbar):

    def __init__(self, master, widgetlist, **kwargs):
        self._widgets = widgetlist
        super().__init__(master, command=self._on_scrollbar, **kwargs)
        for widget in widgetlist:
            widget['yscrollcommand'] = self._on_widget_scroll

    def _on_scrollbar(self, *args):
        """Call the yview methods of all widgets."""
        for widget in self._widgets:
            widget.yview(*args)

    def _on_widget_scroll(self, beginning, end):
        """Set the scrollbar and other widgets to the correct place."""
        self.set(beginning, end)
        self._on_scrollbar('moveto', beginning)


if __name__ == '__main__':
    # simple test
    root = tk.Tk()
    left = tk.Text(width=20)
    left.pack(side='left', fill='both', expand=True)
    right = tk.Text(width=20)
    right.pack(side='left', fill='both', expand=True)
    scrollbar = MultiScrollbar(root, left, right)
    scrollbar.pack(side='right', fill='y')
    for i in range(100):
        left.insert('end-1c', 'left %d\n' % i)
        right.insert('end-1c', 'right %d\n' % i)
    root.mainloop()
