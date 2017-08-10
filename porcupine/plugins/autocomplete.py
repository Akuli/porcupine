import collections
import re

import jedi

import porcupine
from porcupine import tabs, utils

setup_before = ['tabs2spaces']      # see tabs2spaces.py

# Some jedi settings.
jedi.settings.add_bracket_after_function = True


def _jedi_suffix_finder(source, line, col):
    # TODO: Make this into its own module.
    script = jedi.Script(source, line, col)
    return (c.complete for c in script.completions())


class AutoCompleter:
    suffix_finders = {"Python": _jedi_suffix_finder}

    def __init__(self, tab):
        self.tab = tab
        self._startpos = None
        self._suffixes = None
        self._completing = False    # avoid recursion

    def _generic_suffix_finder(self):
        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        match = re.search(r'\w+$', before_cursor)
        if match is None:
            # can't autocomplete based on this
            return None
        prefix = match.group(0)

        # Tcl's regexes don't support \b or a sane way of grouping so
        # they are kind of useless for this. I guess I should implement
        # this with Tcl regexes too and check which is faster :)
        result = set()
        for chunk in self.tab.textwidget.iter_chunks():
            for match in re.finditer(r'\b' + prefix + r'(\w+)', chunk):
                result.add(match.group(1))

        # if the cursor is in the middle of a word, that word must not
        # be completed, e.g. if the user types abcdef and moves the
        # cursor between c and d, we must not autocomplete to abcdefdef
        result.discard(re.search(r'^\w*', after_cursor).group(0))

        return collections.deque(sorted(result, key=str.casefold))

    def _find_suffixes(self):
        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        if re.match(r"^\s*$", before_cursor) is not None:
            # If the line is just whitespace, or empty, we want to indent.
            return None
        elif re.match(r"\w+", after_cursor) is None:
            finder = self.suffix_finders.get(self.tab.filetype.name)

            if finder is None:
                return self._generic_suffix_finder()

            line, col = map(int, self.tab.textwidget.index("insert").split("."))
            source = self.tab.textwidget.get("1.0", "end - 1 char")
            return collections.deque(finder(source, line, col))

        # We don't want to complete in the middle of a word.
        return collections.deque()

    def _complete(self, rotation):
        self._completing = True

        if self._suffixes is None:
            self._startpos = self.tab.textwidget.index('insert')
            self._suffixes = self._find_suffixes()
            if self._suffixes is None:
                # no completable characters before the cursor, just give
                # up and allow doing something else on this tab press
                return None
            self._suffixes.appendleft('')  # end of completions

        self._suffixes.rotate(rotation)
        self.tab.textwidget.delete(self._startpos, 'insert')
        self.tab.textwidget.mark_set('insert', self._startpos)
        self.tab.textwidget.insert(self._startpos, self._suffixes[0])

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
    if isinstance(tab, tabs.FileTab):
        completer = AutoCompleter(tab)
        utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
        tab.textwidget.bind('<<CursorMoved>>', completer.reset, add=True)


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)


def completer(filetype):
    """
    Decorator that allows you to add a syntax completer for a specific filetype
    """

    def _inner(func):
        AutoCompleter.suffix_finders[filetype] = func
        return func

    return _inner
