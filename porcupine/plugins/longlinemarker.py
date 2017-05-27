"""Maximum line length marker for Tkinter's text widget."""

import tkinter as tk
import tkinter.font as tkfont

from porcupine import tabs
from porcupine.settings import config, color_themes


class LongLineMarker(tk.Frame):

    def __init__(self, textwidget):
        super().__init__(textwidget, width=1)
        self._height = 0   # set_height() will be called

    def set_theme_name(self, name):
        self['bg'] = color_themes[name]['errorbackground']

    def do_update(self, junk=None):
        font = tkfont.Font(name='TkFixedFont', exists=True)
        where = font.measure(' ' * config['Editing', 'maxlinelen'])
        self.place(x=where, height=self._height)

    def on_configure(self, event):
        self._height = event.height
        self.do_update()

    def destroy(self):
        super().destroy()


def tab_callback(tab):
    if not isinstance(tab, tabs.FileTab):
        yield
        return

    marker = LongLineMarker(tab.textwidget)

    def on_settings_changed(section, key, value):
        if section == 'Font' or (section, key) == ('Editing', 'maxlinelen'):
            marker.do_update()
        elif section == 'Editing' and key == 'color_theme':
            marker.set_theme_name(value)

    tab.textwidget.bind('<Configure>', marker.on_configure, add=True)
    config.anything_changed_hook.connect(on_settings_changed)
    yield
    config.anything_changed_hook.disconnect(on_settings_changed)
    # destroying the textwidget will destroy the marker


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)


if __name__ == '__main__':
    from porcupine.settings import load as load_settings
    root = tk.Tk()
    load_settings()
    text = tk.Text(root)
    text.pack(fill='both', expand=True)
    marker = LongLineMarker(text)
    text.bind('<Configure>', lambda event: marker.set_height(event.height))
    root.mainloop()
