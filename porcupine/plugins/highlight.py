"""Syntax highlighting for Tkinter's text widget with Pygments."""
# TODO: optimize by not always highlighting everything and may be get
#       rid of the multiprocessing stuff? alternatively, at least don't
#       make a separate process for each file!
# TODO: if a tag goes all the way to end of line, extend it past it to
#       hide the lagging at least a little bit (if we're not
#       highlighting it line by line

import multiprocessing
import queue
import tkinter.font as tkfont

import pygments.styles
import pygments.token
import pygments.util   # only for ClassNotFound, the docs say that it's here

from porcupine import filetypes, get_tab_manager, settings, tabs, utils

config = settings.get_section('General')


def _list_all_token_types(tokentype):
    yield tokentype
    for sub in map(_list_all_token_types, tokentype.subtypes):
        yield from sub

_ALL_TAGS = set(map(str, _list_all_token_types(pygments.token.Token)))  # noqa


# tokenizing with pygments is the bottleneck of this thing (at least on
# CPython) so it's done in another process
class PygmentizerProcess:

    def __init__(self):
        self.in_queue = multiprocessing.Queue()   # contains strings
        self.out_queue = multiprocessing.Queue()  # dicts from _pygmentize()
        self.process = multiprocessing.Process(target=self._run)
        self.process.start()

    # returns {str(tokentype): [start1, end1, start2, end2, ...]}
    def _pygmentize(self, filetype, code):
        # pygments doesn't include any info about where the tokens are
        # so we need to do it manually :(
        lineno = 1
        column = 0
        lexer = filetype.get_lexer(stripnl=False)

        result = {}
        for tokentype, string in lexer.get_tokens(code):
            start = '%d.%d' % (lineno, column)
            if '\n' in string:
                lineno += string.count('\n')
                column = len(string.rsplit('\n', 1)[1])
            else:
                column += len(string)
            end = '%d.%d' % (lineno, column)
            result.setdefault(str(tokentype), []).extend([start, end])

        return result

    def _run(self):
        while True:
            # if multiple codes were queued while this thing was doing
            # the previous code, just do the last one and ignore the rest
            args = self.in_queue.get(block=True)
            try:
                while True:
                    args = self.in_queue.get(block=False)
                    # print("_run: ignoring a code")
            except queue.Empty:
                pass

            result = self._pygmentize(*args)
            self.out_queue.put(result)


class Highlighter:

    def __init__(self, textwidget, filetype_getter):
        self.textwidget = textwidget
        self._get_filetype = filetype_getter
        self.pygmentizer = PygmentizerProcess()

        # the tags use fonts from here
        self._fonts = {}
        for bold in (True, False):
            for italic in (True, False):
                # the fonts will be updated later, see _on_config_changed()
                self._fonts[(bold, italic)] = tkfont.Font(
                    weight=('bold' if bold else 'normal'),
                    slant=('italic' if italic else 'roman'))

        config.connect('pygments_style', self._on_config_changed,
                       run_now=False)
        config.connect('font_family', self._on_config_changed, run_now=False)
        config.connect('font_size', self._on_config_changed, run_now=False)
        self._on_config_changed()
        self.textwidget.after(50, self._do_highlights)

    def on_destroy(self, junk=None):
        config.disconnect('pygments_style', self._on_config_changed)
        config.disconnect('font_family', self._on_config_changed)
        config.disconnect('font_size', self._on_config_changed)

        #print("terminating", repr(self.pygmentizer.process))
        self.pygmentizer.process.terminate()
        #print("terminated", repr(self.pygmentizer.process))

    def _on_config_changed(self, junk=None):
        # when the font family or size changes, self.textwidget['font']
        # also changes because it's a porcupine.textwiddet.ThemedText widget
        fontobject = tkfont.Font(name=self.textwidget['font'], exists=True)
        font_updates = fontobject.actual()
        del font_updates['weight']     # ignore boldness
        del font_updates['slant']      # ignore italicness

        for (bold, italic), font in self._fonts.items():
            # fonts don't have an update() method
            for key, value in font_updates.items():
                font[key] = value

        # http://pygments.org/docs/formatterdevelopment/#styles
        # all styles seem to yield all token types when iterated over,
        # so we should always end up with the same tags configured
        style = pygments.styles.get_style_by_name(config['pygments_style'])
        for tokentype, infodict in style:
            # this doesn't use underline and border
            # i don't like random underlines in my code and i don't know
            # how to implement the border with tkinter
            key = (infodict['bold'], infodict['italic'])   # pep8 line length
            kwargs = {'font': self._fonts[key]}
            if infodict['color'] is None:
                kwargs['foreground'] = ''    # reset it
            else:
                kwargs['foreground'] = '#' + infodict['color']
            if infodict['bgcolor'] is None:
                kwargs['background'] = ''
            else:
                kwargs['background'] = '#' + infodict['bgcolor']

            self.textwidget.tag_config(str(tokentype), **kwargs)

            # make sure that the selection tag takes precedence over our
            # token tag
            self.textwidget.tag_lower(str(tokentype), 'sel')

    # handle things from the highlighting process
    def _do_highlights(self):
        # this check is actually unnecessary; turns out that destroying
        # the text widget stops this timeout because the text widget's
        # after method was used, but i don't feel like relying on it
        if not self.pygmentizer.process.is_alive():
            return

        # if the pygmentizer process has put multiple result dicts to
        # the queue, only use the last one
        tags2add = None
        try:
            while True:
                tags2add = self.pygmentizer.out_queue.get(block=False)
        except queue.Empty:
            pass

        if tags2add is not None:
            # print("_do_highlights: got something")
            for tag in _ALL_TAGS:
                self.textwidget.tag_remove(tag, '0.0', 'end')
            for tag, places in tags2add.items():
                self.textwidget.tag_add(tag, *places)

        # 50 milliseconds doesn't seem too bad, bigger timeouts tend to
        # make things laggy
        self.textwidget.after(50, self._do_highlights)

    def highlight_all(self, junk=None):
        code = self.textwidget.get('1.0', 'end - 1 char')
        self.pygmentizer.in_queue.put([self._get_filetype(), code])


def on_new_tab(event):
    tab = event.data_widget()
    if not isinstance(tab, tabs.FileTab):
        return

    highlighter = Highlighter(tab.textwidget, (lambda: tab.filetype))
    tab.bind('<<FiletypeChanged>>', highlighter.highlight_all, add=True)
    tab.textwidget.bind('<<ContentChanged>>', highlighter.highlight_all,
                        add=True)
    tab.bind('<Destroy>', highlighter.on_destroy, add=True)
    highlighter.highlight_all()


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)


if __name__ == '__main__':
    # simple test
    # FIXME: doesnt work
    import tkinter
    from porcupine.settings import load as load_settings

    def on_modified(event):
        text.unbind('<<Modified>>')
        text.edit_modified(False)
        text.bind('<<Modified>>', on_modified)
        text.after_idle(highlighter.highlight_all)

    root = tkinter.Tk()
    load_settings()     # must be after creating root window
    text = tkinter.Text(root, insertbackground='red')
    text.pack(fill='both', expand=True)
    text.bind('<<Modified>>', on_modified)

    # The theme doesn't display perfectly here because the highlighter
    # only does tags, not foreground, background etc. See textwidget.py.
    highlighter = Highlighter(
        text, (lambda: filetypes.get_filetype_by_name('Python')))

    with open(__file__, 'r') as f:
        text.insert('1.0', f.read())
    text.see('end')

    try:
        root.mainloop()
    finally:
        highlighter.on_destroy()
