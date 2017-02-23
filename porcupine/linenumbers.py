"""Line numbers for tkinter's Text widget.

This doesn't handle scrolling in any way. See multiscrollbar.py.
"""

import tkinter as tk


class LineNumbers(tk.Text):

    def __init__(self, *args, width=6, **kwargs):
        """Initialize the line number widget."""
        super().__init__(*args, width=width, **kwargs)
        self.insert('1.0', " 1")    # this is always there
        self['state'] = 'disabled'
        self._linecount = 1

    def do_update(self, linecount):
        """This should be ran when the line count changes."""
        if linecount > self._linecount:
            # add more linenumbers
            self['state'] = 'normal'
            for i in range(self._linecount + 1, linecount + 1):
                self.insert('end-1c', '\n %d' % i)
            self['state'] = 'disabled'
        if linecount < self._linecount:
            # delete the linenumbers we don't need
            self['state'] = 'normal'
            self.delete('%d.0+1l-1c' % linecount, 'end-1c')
            self['state'] = 'disabled'
        self._linecount = linecount


if __name__ == '__main__':
    # simple test/demo
    root = tk.Tk()
    text = tk.Text(root)
    linenumbers = LineNumbers(root, text)
    linenumbers.pack(side='left', fill='y')
    text.pack(side='left', fill='both', expand=True)

    def do_the_update():
        linecount = int(text.index('end-1c').split('.')[0])
        linenumbers.do_update(linecount)

    def on_lineno_change(event):
        text.after_idle(do_the_update)

    # this isn't perfect but this is good enough for this test
    text.bind('<Return>', on_lineno_change)
    text.bind('<BackSpace>', on_lineno_change)
    text.bind('<Delete>', on_lineno_change)

    root.mainloop()
