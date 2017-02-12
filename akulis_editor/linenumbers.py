"""Line numbers for tkinter's Text widget.

This doesn't handle scrolling in any way. See multiscrollbar.py.
"""

import tkinter as tk


class LineNumbers(tk.Text):

    def __init__(self, master, textwidget, **kwargs):
        """Initialize the line number widget."""
        super().__init__(master, width=6, **kwargs)
        self.insert('1.0', ' 1')
        self['state'] = 'disabled'
        self._textwidget = textwidget
        self._linecount = 1

    def do_update(self):
        """This should be ran when the line count changes."""
        linecount = int(self._textwidget.index('end-1c').split('.')[0])
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


class DummyLineNumbers:
    """A class with a do_update() method that does nothing.
    
    This is used instead of LineNumbers when line numbers are disabled 
    in the configuration.
    """
    
    def do_update(self):
        pass


if __name__ == '__main__':
    # simple test/demo
    root = tk.Tk()
    text = tk.Text(root)
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
