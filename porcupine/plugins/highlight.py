"""Syntax highlighting for Tkinter's text widget with Pygments."""
# TODO: optimize by not always highlighting everything and may be get
#       rid of the multiprocessing stuff? alternatively, at least don't
#       make a separate process for each file!
# TODO: if a tag goes all the way to end of line, extend it past it to
#       hide the lagging at least a little bit (if we're not
#       highlighting it line by line

import multiprocessing
import queue

import pygments.styles
import pygments.token
import pygments.util   # only for ClassNotFound, the docs say that it's here
import teek

from porcupine import get_tab_manager, settings, tabs

config = settings.get_section('General')


def _list_all_token_types(tokentype):
    yield tokentype
    for sub in map(_list_all_token_types, tokentype.subtypes):
        yield from sub


# tokenizing with pygments is the bottleneck of this thing (at least on
# CPython) so it's done in another process
class PygmentizerProcess:

    def __init__(self):
        self.in_queue = multiprocessing.Queue()   # contains strings
        self.out_queue = multiprocessing.Queue()  # dicts from _pygmentize()
        self.process = multiprocessing.Process(target=self._run)
        self.process.start()

    # returns {str(tokentype): [(start1, end1), (start2, end2), ...]}
    def _pygmentize(self, filetype, code):
        # pygments doesn't include any info about where the tokens are
        # so we need to do it manually :(
        lineno = 1
        column = 0
        lexer = filetype.get_lexer(stripnl=False)

        result = {}
        for tokentype, string in lexer.get_tokens(code):
            start = (lineno, column)
            if '\n' in string:
                lineno += string.count('\n')
                column = len(string.rsplit('\n', 1)[1])
            else:
                column += len(string)
            end = (lineno, column)
            result.setdefault(str(tokentype), []).append((start, end))

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

        tag_names = set(map(str, _list_all_token_types(pygments.token.Token)))
        self.all_tags = [self.textwidget.get_tag(name) for name in tag_names]

        # the tags use fonts from here
        self._fonts = {}
        for bold in (True, False):
            for italic in (True, False):
                # the fonts will be updated later, see _on_config_changed()
                self._fonts[(bold, italic)] = teek.NamedFont(
                    weight=('bold' if bold else 'normal'),
                    slant=('italic' if italic else 'roman'))

        config.connect('pygments_style', self._on_config_changed,
                       run_now=False)
        config.connect('font_family', self._on_config_changed, run_now=False)
        config.connect('font_size', self._on_config_changed, run_now=False)
        self._on_config_changed()
        teek.after(50, self._do_highlights)

    def on_destroy(self):
        config.disconnect('pygments_style', self._on_config_changed)
        config.disconnect('font_family', self._on_config_changed)
        config.disconnect('font_size', self._on_config_changed)

        #print("terminating", repr(self.pygmentizer.process))
        self.pygmentizer.process.terminate()
        #print("terminated", repr(self.pygmentizer.process))

    def _on_config_changed(self, junk_config_value=None):
        # the text widget uses TkFixedFont
        for (bold, italic), font in self._fonts.items():
            font.family = teek.NamedFont('TkFixedFont').family
            font.size = teek.NamedFont('TkFixedFont').size

        # http://pygments.org/docs/formatterdevelopment/#styles
        # all styles seem to yield all token types when iterated over,
        # so we should always end up with the same tags configured
        style = pygments.styles.get_style_by_name(config['pygments_style'])
        for tokentype, infodict in style:
            # this doesn't use underline and border
            # i don't like random underlines in my code and i don't know
            # how to implement the border with tk
            key = (infodict['bold'], infodict['italic'])   # pep8 line length
            configs = {'font': self._fonts[key]}
            if infodict['color'] is None:
                configs['foreground'] = ''    # reset it
            else:
                configs['foreground'] = '#' + infodict['color']
            if infodict['bgcolor'] is None:
                configs['background'] = ''
            else:
                configs['background'] = '#' + infodict['bgcolor']

            self.textwidget.get_tag(str(tokentype)).update(configs)

            # make sure that the selection tag takes precedence over our
            # token tag
            # TODO: add 'tag lower' to teek
            teek.tcl_call(None, self.textwidget, 'tag', 'lower',
                          str(tokentype), 'sel')

    # handle things from the highlighting process
    # TODO: use teek.init_threads() stuff here?
    def _do_highlights(self):
        # this check is kinda not necessary; turns out that quitting porcupine
        # stops this timeout, but i don't feel like relying on it
        if not self.pygmentizer.process.is_alive():
            return

        # if the pygmentizer process has put multiple result dicts to
        # the queue, only use the last one, this prevents slowness when typing
        # fast
        tags2add = None
        try:
            while True:
                tags2add = self.pygmentizer.out_queue.get(block=False)
        except queue.Empty:
            pass

        if tags2add is not None:
            # print("_do_highlights: got something")
            for tag in self.all_tags:
                tag.remove()
            for tagname, places in tags2add.items():
                tag = self.textwidget.get_tag(tagname)
                for start, end in places:
                    tag.add(start, end)

        # 50 milliseconds doesn't seem too bad, bigger timeouts tend to
        # make things laggy
        teek.after(50, self._do_highlights)

    def highlight_all(self):
        code = self.textwidget.get()
        self.pygmentizer.in_queue.put((self._get_filetype(), code))


def on_new_tab(tab):
    if not isinstance(tab, tabs.FileTab):
        return

    highlighter = Highlighter(tab.textwidget, (lambda: tab.filetype))
    tab.on_filetype_changed.connect(highlighter.highlight_all)
    tab.textwidget.bind('<<ContentChanged>>', highlighter.highlight_all)
    tab.textwidget.bind('<Destroy>', highlighter.on_destroy)
    highlighter.highlight_all()


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
