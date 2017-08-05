import collections
import re

import porcupine
from porcupine import tabs, utils


class AutoCompleter:

    def __init__(self, textwidget):
        self.textwidget = textwidget
        self._startpos = None
        self._suffixes = None
        self._completing = False    # avoid recursion

    def _find_suffixes(self):
        before_cursor = self.textwidget.get('insert linestart', 'insert')
        after_cursor = self.textwidget.get('insert', 'insert lineend')

        match = re.search('\w+$', before_cursor)
        if match is None:
            # can't autocomplete based on this
            return None
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

    def _complete(self, rotation):
        self._completing = True

        if self._suffixes is None:
            self._startpos = self.textwidget.index('insert')
            self._suffixes = self._find_suffixes()
            if self._suffixes is None:
                # no completable characters before the cursor, just give
                # up and allow doing something else on this tab press
                return None
            self._suffixes.appendleft('')  # end of completions

        self._suffixes.rotate(rotation)
        self.textwidget.delete(self._startpos, 'insert')
        self.textwidget.mark_set('insert', self._startpos)
        self.textwidget.insert(self._startpos, self._suffixes[0])

        self._completing = False
        return 'break'

    def on_tab(self, event, shifted):
        if event.widget.tag_ranges('sel'):
            # something's selected, autocompleting is probably not the
            # right thing to do
            return None

        if shifted:       # display the previous completion
            return self._complete(1)
        else:
            return self._complete(-1)

    def reset(self, *junk):
        # deleting and inserting from _complete() runs this, so this
        # must do nothing if we're currently completing
        if not self._completing:
            self._suffixes = None


def on_new_tab(event):
    # TODO: autocomplete in other kinds of tabs too?
    tab = event.widget.tabs[-1]
    if not isinstance(tab, tabs.FileTab):
        return

    def on_destroy(event):
        tab.textwidget.cursor_move_hook.disconnect(completer.reset)

    completer = AutoCompleter(tab.textwidget)
    utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)

    tab.textwidget.cursor_move_hook.connect(completer.reset)
    tab.textwidget.bind('<Destroy>', on_destroy)


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)
