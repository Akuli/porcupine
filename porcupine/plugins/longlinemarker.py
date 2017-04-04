"""Maximum line length marker for Tkinter's text widget."""

import tkinter as tk
import tkinter.font as tkfont

from porcupine import plugins
from porcupine.settings import config, color_themes


class LongLineMarker(tk.Frame):

    def __init__(self, textwidget):
        super().__init__(textwidget, width=1)
        self._height = 0   # set_height should be called
        for key in ['editing:longlinemarker', 'editing:maxlinelen',
                    'editing:font', 'editing:color_theme']:
            config.connect(key, self._on_config_changed)
            self._on_config_changed(key, config[key])

    def _on_config_changed(self, key, value):
        if key == 'editing:color_theme':
            self['bg'] = color_themes[value]['longlinemarker']
        else:
            if config['editing:longlinemarker']:
                font = tkfont.Font(font=config['editing:font'])
                x = font.measure(' ' * config['editing:maxlinelen'])
                self.place(x=x, height=self._height)
            else:
                self.place_forget()

    def set_height(self, height):
        self._height = height
        if config['editing:longlinemarker']:
            self.place(height=self._height)


def filetab_hook(filetab):
    marker = LongLineMarker(filetab.textwidget)
    filetab.textwidget.bind(
        '<Configure>', lambda event: marker.set_height(event.height))


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
