"""Maximum line length marker for Tkinter's text widget."""

import tkinter as tk
import tkinter.font as tkfont

import pygments.styles
import pygments.token

from porcupine import tabs
from porcupine.settings import config


class LongLineMarker(tk.Frame):

    def __init__(self, textwidget):
        super().__init__(textwidget, width=1)
        self._height = 0        # on_configure() will run later

        config.connect('Font', 'family', self.do_update)
        config.connect('Font', 'size', self.do_update)
        config.connect('Editing', 'maxlinelen', self.do_update)
        self.do_update()
        config.connect('Editing', 'pygments_style',
                       self.on_style_changed, run_now=True)

    def destroy(self):
        config.disconnect('Font', 'family', self.do_update)
        config.disconnect('Font', 'size', self.do_update)
        config.disconnect('Editing', 'maxlinelen', self.do_update)
        config.disconnect('Editing', 'pygments_style', self.on_style_changed)
        super().destroy()

    def do_update(self, junk=None):
        # self.master is the text widget, tkinter set it in __init__
        font = tkfont.Font(name=self.master['font'], exists=True)
        where = font.measure(' ' * config['Editing', 'maxlinelen'])
        self.place(x=where, height=self._height)

    def on_style_changed(self, name):
        # styles have a style_for_token() method, but only iterating is
        # documented :( http://pygments.org/docs/formatterdevelopment/
        # dict(iterable_of_pairs) ftw, i'm using iter() to make sure
        # that dict() really treats it as an iterable of pairs
        infos = dict(iter(pygments.styles.get_style_by_name(name)))
        for tokentype in [pygments.token.Error, pygments.token.Name.Exception]:
            if tokentype in infos:
                for key in ['bgcolor', 'color', 'border']:
                    if infos[tokentype][key] is not None:
                        self['bg'] = '#' + infos[tokentype][key]
                        return

        # stupid fallback
        self['bg'] = 'red'

    # bind <Configure> to this
    def on_configure(self, event):
        self._height = event.height
        self.do_update()


def tab_callback(tab):
    if not isinstance(tab, tabs.FileTab):
        yield
        return

    marker = LongLineMarker(tab.textwidget)
    tab.textwidget.bind('<Configure>', marker.on_configure, add=True)
    yield
    # destroying the textwidget will destroy the marker


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)


if __name__ == '__main__':
    root = tk.Tk()
    config.load()
    text = tk.Text(root)
    text.pack(fill='both', expand=True)

    marker = LongLineMarker(text)
    text.bind('<Configure>', marker.on_configure)
    root.mainloop()
