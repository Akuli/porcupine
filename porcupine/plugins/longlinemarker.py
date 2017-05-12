"""Maximum line length marker for Tkinter's text widget."""

import tkinter as tk
import tkinter.font as tkfont

from porcupine import plugins
from porcupine.settings import config, color_themes


class LongLineMarker(tk.Frame):

    def __init__(self, textwidget):
        super().__init__(textwidget, width=1)
        self._height = 0   # set_height() will be called

    def set_theme_name(self, name):
        self['bg'] = color_themes[name]['errorbackground']

    def update(self, junk=None):
        family, size = config.get_font('Editing', 'font')
        font = tkfont.Font(family=family, size=size)
        where = font.measure(' ' * config['Editing'].getint('maxlinelen'))
        self.place(x=where, height=self._height)

    def set_height(self, height):
        self._height = height
        self.update()


def filetab_hook(filetab):
    marker = LongLineMarker(filetab.textwidget)

    def configure_callback(event):
        marker.set_height(event.height)

    with config.connect('Editing', 'color_theme', marker.set_theme_name):
        with config.connect('Editing', 'maxlinelen', marker.update):
            with config.connect('Editing', 'font', marker.update):
                filetab.textwidget.bind(
                    '<Configure>', configure_callback, add=True)
                yield
    marker.destroy()


plugins.add_plugin("Long Line Marker", filetab_hook=filetab_hook)


if __name__ == '__main__':
    from porcupine.settings import load as load_settings
    root = tk.Tk()
    load_settings()
    text = tk.Text(root)
    text.pack(fill='both', expand=True)
    marker = LongLineMarker(text)
    text.bind('<Configure>', lambda event: marker.set_height(event.height))
    root.mainloop()
