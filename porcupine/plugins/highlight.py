"""Syntax highlighting for Tkinter's text widget with Pygments."""
# TODO: optimize by not always highlighting everything and may be get
#       rid of the multiprocessing stuff? alternatively, at least don't
#       make a separate process for each file!
# TODO: if a tag goes all the way to end of line, extend it past it to
#       hide the lagging at least a little bit (if we're not
#       highlighting it line by line
# TODO: better support for different languages in the rest of the editor

import functools
import multiprocessing
import queue
import re
import tkinter as tk
import tkinter.font as tkfont

import pygments.styles
import pygments.token
import pygments.util   # only for ClassNotFound, the docs say that it's here

from porcupine import filetypes, tabs
from porcupine.settings import config


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
    # TODO: send the actual FileType object instead of its name when
    # FileTypes will support pickling
    def _pygmentize(self, filetype_name, code):
        # pygments doesn't include any info about where the tokens are
        # so we need to do it manually :(
        lineno = 1
        column = 0
        lexer = filetypes.filetypes[filetype_name].get_lexer()

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

    def __init__(self, textwidget, filetype_name_getter):
        self.textwidget = textwidget
        self._get_filetype_name = filetype_name_getter
        self.pygmentizer = PygmentizerProcess()

        # the tags use fonts from here
        self._fonts = {}
        for bold in (True, False):
            for italic in (True, False):
                # the fonts will be updated later, see _on_config_changed()
                self._fonts[(bold, italic)] = tkfont.Font(
                    weight=('bold' if bold else 'normal'),
                    slant=('italic' if italic else 'roman'))

        config.connect('Editing', 'pygments_style', self._on_config_changed)
        config.connect('Font', 'family', self._on_config_changed)
        config.connect('Font', 'size', self._on_config_changed)
        self._on_config_changed()
        self.textwidget.after(50, self._do_highlights)

    def destroy(self):
        config.disconnect('Editing', 'pygments_style', self._on_config_changed)
        config.disconnect('Font', 'family', self._on_config_changed)
        config.disconnect('Font', 'size', self._on_config_changed)

        # print("terminating", repr(self.pygmentizer.process))
        self.pygmentizer.process.terminate()
        # print("terminated", repr(self.pygmentizer.process))

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
        style = pygments.styles.get_style_by_name(
            config['Editing', 'pygments_style'])

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
        self.pygmentizer.in_queue.put([self._get_filetype_name(), code])


def tab_callback(tab):
    if not isinstance(tab, tabs.FileTab):
        yield
        return

    highlighter = Highlighter(tab.textwidget, (lambda: tab.filetype.name))
    tab.path_changed_hook.connect(highlighter.highlight_all)
    tab.textwidget.modified_hook.connect(highlighter.highlight_all)
    highlighter.highlight_all()
    yield
    highlighter.destroy()
    tab.textwidget.modified_hook.disconnect(highlighter.highlight_all)
    tab.path_changed_hook.disconnect(highlighter.highlight_all)


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)


if __name__ == '__main__':
    # simple test
    from porcupine.settings import load as load_settings

    def on_modified(event):
        text.unbind('<<Modified>>')
        text.edit_modified(False)
        text.bind('<<Modified>>', on_modified)
        text.after_idle(highlighter.highlight_all)

    root = tk.Tk()
    load_settings()     # must be after creating root window
    text = tk.Text(root, insertbackground='red')
    text.pack(fill='both', expand=True)
    text.bind('<<Modified>>', on_modified)

    # The theme doesn't display perfectly here because the highlighter
    # only does tags, not foreground, background etc. See textwidget.py.
    highlighter = Highlighter(text, (lambda: 'Python'))

    with open(__file__, 'r') as f:
        text.insert('1.0', f.read())
    text.see('end')

    try:
        root.mainloop()
    finally:
        highlighter.destroy()
