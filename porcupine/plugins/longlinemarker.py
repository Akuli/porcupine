"""Maximum line length marker for Tkinter's text widget."""
# TODO: support horizontal scrolling

import pygments.styles
import pygments.token
import pythotk as tk

from porcupine import get_tab_manager, settings, tabs

config = settings.get_section('General')


class LongLineMarker:

    def __init__(self, filetab):
        self.tab = filetab

        # this must not be a ttk frame because the background color
        # comes from the pygments style, not from the ttk theme
        self.frame_command = filetab.textwidget.to_tcl() + '.longlinemarker'
        tk.tcl_call(None, 'frame', self.frame_command, '-width', '1')
        self._height = 0        # on_configure() will run later

    def setup(self):
        config.connect('font_family', self.do_update, run_now=False)
        config.connect('font_size', self.do_update, run_now=False)
        config.connect('pygments_style', self.on_style_changed)
        self.tab.textwidget.bind('<Configure>', self.on_configure, event=True)
        self.tab.on_filetype_changed.connect(self.do_update)
        self.tab.textwidget.bind('<Destroy>', self.on_destroy)
        self.do_update()

    def on_destroy(self):
        config.disconnect('font_family', self.do_update)
        config.disconnect('font_size', self.do_update)
        config.disconnect('pygments_style', self.on_style_changed)

    def do_update(self):
        column = self.tab.filetype.max_line_length
        if column == 0:
            # maximum line length is disabled, see filetypes.ini docs
            tk.tcl_call(None, 'place', 'forget', self.frame_command)
        else:
            font = tk.NamedFont('TkFixedFont')
            where = font.measure(' ' * column)
            tk.tcl_call(None, 'place', self.frame_command,
                        '-x', where, '-height', self._height)

    def on_style_changed(self, name):
        # do the same thing as porcupine's color theme menu does
        infos = dict(iter(pygments.styles.get_style_by_name(name)))
        for tokentype in [pygments.token.Error, pygments.token.Name.Exception]:
            if tokentype in infos:
                for key in ['bgcolor', 'color', 'border']:
                    if infos[tokentype][key] is not None:
                        tk.tcl_call(None, self.frame_command, 'configure',
                                    '-bg', '#' + infos[tokentype][key])
                        return

        # stupid fallback
        tk.tcl_call(None, self.frame_command, 'configure', '-bg', 'red')

    def on_configure(self, event):
        self._height = event.height
        self.do_update()


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        LongLineMarker(tab).setup()


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
