"""Line numbers for tkinter's Text widget.

This doesn't handle scrolling in any way. See multiscrollbar.py.
"""

import tkinter as tk

from porcupine.settings import config, color_themes


class LineNumbers(tk.Text):

    def __init__(self, parent, textwidget, width=6, **kwargs):
        """Initialize the line number widget."""
        super().__init__(parent, width=width, font=textwidget['font'],
                         **kwargs)
        self.textwidget = textwidget
        self.insert('1.0', " 1")    # this is always there
        self['state'] = 'disabled'  # must be after the insert
        self._linecount = 1

        config.connect('editing:color_theme', self._on_theme_changed)
        self._on_theme_changed(None, config['editing:color_theme'])

    def _on_theme_changed(self, junk, value):
        self['fg'] = color_themes[value]['foreground']
        self['bg'] = color_themes[value]['background']

    def do_update(self):
        """This should be ran when the line count changes."""
        linecount = int(self.textwidget.index('end-1c').split('.')[0])
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
    import porcupine.settings

    root = tk.Tk()
    porcupine.settings.load()

    theme = color_themes[config['editing:color_theme']]
    text = tk.Text(root, fg=theme['foreground'], bg=theme['background'])
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
