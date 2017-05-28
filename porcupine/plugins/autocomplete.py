import collections
import re
import tkinter as tk

from porcupine import tabs


class AutoCompleter:

    def __init__(self, textwidget):
        self.textwidget = textwidget
        self._startpos = None
        self._suffixes = None
        self._completing = False

    def _find_suffixes(self):
        before_cursor = self.textwidget.get('insert linestart', 'insert')
        after_cursor = self.textwidget.get('insert', 'insert lineend')

        match = re.search('\w+$', before_cursor)
        if match is None:
            # can't autocomplete based on this
            return collections.deque()
        prefix = match.group(0)

        # Tcl's regexes don't support \b or a sane way of grouping so
        # they are kind of useless for this. I guess I should implement
        # this with Tcl regexes too and check which is faster :)
        result = set()
        for chunk in self.textwidget.iter_chunks():
            for match in re.finditer(r'\b' + prefix + r'(\w+)', chunk):
                result.add(match.group(1))

        # if the cursor is in the middle of a word, that word must not
        # be completed, e.g. if the user types abcdef and moves the
        # cursor between c and d, we must not autocomplete to abcdefdef
        result.discard(re.search('^\w*', after_cursor).group(0))

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
    if not isinstance(tab, tabs.FileTab):
        # TODO: autocomplete in some other tabs too?
        yield
        return

    completer = AutoCompleter(tab.textwidget)

    def do_reset(*junk):
        completer.reset()

    tab.textwidget.complete_hook.connect(completer.complete)
    tab.textwidget.cursor_move_hook.connect(do_reset)
    yield
    tab.textwidget.complete_hook.disconnect(completer.complete)
    tab.textwidget.cursor_move_hook.disconnect(do_reset)


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)
