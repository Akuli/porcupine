import collections
import re
import tkinter as tk

from porcupine import filetabs


class AutoCompleter:

    def __init__(self, textwidget):
        self.textwidget = textwidget
        self._startpos = None
        self._suffixes = None
        self._completing = False

    def _find_suffixes(self):
        # TODO: what if there's text on both sides of the cursor? currently
        # this is treated as one long word that the cursor is a part of, and
        # it's kind of confusing
        lineno = int(self.textwidget.index('insert').split('.')[0])
        before_cursor = self.textwidget.get('%d.0' % lineno, 'insert')

        match = re.search('\w+$', before_cursor)
        if match is None:
            # can't autocomplete based on this
            return collections.deque()
        prefix = match.group(0)

        # Tcl's regexes don't support \b or a sane way of grouping so
        # they are kind of useless for this
        # TODO: ignore the word that the cursor is on top of if any
        result = set()
        for chunk in self.textwidget.iter_chunks():
            for match in re.finditer(r'\b' + prefix + r'(\w+)', chunk):
                result.add(match.group(1))
        return collections.deque(sorted(result, key=str.casefold))

    def complete(self, prev_or_next):
        self._completing = True

        try:
            if self._startpos is None:
                # not completing yet
                self._startpos = self.textwidget.index('insert')
                self._suffixes = self._find_suffixes()
                self._suffixes.appendleft('')  # end of completions

            self._suffixes.rotate(-1 if prev_or_next == 'next' else 1)
            self.textwidget.delete(self._startpos, 'insert')
            self.textwidget.mark_set('insert', self._startpos)
            self.textwidget.insert(self._startpos, self._suffixes[0])

        finally:
            self._completing = False

    def reset(self):
        # deleting and inserting text might run this if this is a
        # callback, so this must do nothing if we're currently
        # completing
        if not self._completing:
            self._suffixes = None
            self._startpos = None


def tab_callback(tab):
    if not isinstance(tab, filetabs.FileTab):
        # TODO: autocomplete in some other tabs too?
        yield
        return

    completer = AutoCompleter(tab.textwidget)

    def do_reset(*junk):
        completer.reset()

    text = tab.textwidget
    text.complete_hook.connect(completer.complete)
    text.cursor_move_hook.connect(do_reset)
    yield
    text.complete_hook.disconnect(completer.complete)
    text.cursor_move_hook.disconnect(do_reset)


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)


if __name__ == '__main__':
    # simple test
    from porcupine import textwidget
    from porcupine.settings import load as load_settings

    def on_tab(event):
        completer.complete('next')
        return 'break'

    def on_shift_tab(event):
        completer.complete('previous')
        return 'break'

    # <<Modified>> is not really correct, the real editor resets on
    # cursor movement instead
    def on_modified(event):
        text.unbind('<<Modified>>')
        text.edit_modified(False)
        text.bind('<<Modified>>', on_modified)
        completer.reset()

    root = tk.Tk()
    load_settings()

    text = textwidget.MainText(root)
    text.iter_chunks = lambda: [text.get('1.0', 'end-1c')]    # lol
    text.pack()

    completer = AutoCompleter(text)
    text.bind('<<Modified>>', on_modified)
    text.bind('<Tab>', on_tab)
    if root.tk.call('tk', 'windowingsystem') == 'x11':
        text.bind('<ISO_Left_Tab>', on_shift_tab)
    else:
        text.bind('<Shift-Tab>', on_shift_tab)

    root.mainloop()
