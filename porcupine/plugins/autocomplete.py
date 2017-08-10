# TODO: document this module's simple register_completer() api
import collections
import re

import jedi

import porcupine
from porcupine import tabs, utils

__all__ = ['register_completer']
setup_before = ['tabs2spaces']      # see tabs2spaces.py
jedi.settings.add_bracket_after_function = True

_suffix_finders = {}


def register_completer(filetype_name, function):
    """Add a syntax completer for a specific filetype.

    Use like this::

        from porcupine.plugins import autocomplete

        def java_completer(script, cursor_lineno, cursor_column):
            # script is the full content of the file
            # this should return an iterable of things that can be inserted
            # after the current cursor position, or an empty iterable
            # (e.g. []) for no completions

        autocomplete.register_completer("Java", java_completer)

    The *filetype_name* should be a key of
    :data:`porcupine.filetypes.filetypes`. Using this decorator multiple
    times with the same *filetype_name* overrides previous decoratings.
    """
    def inner(func):
        _AutoCompleter._suffix_finders[filetype_name] = func
        return func

    return inner


def _jedi_suffix_finder(source, line, column):
    # TODO: Make this into its own module.
    script = jedi.Script(source, line, column)
    return (c.complete for c in script.completions())


class _AutoCompleter:

    def __init__(self, tab):
        self.tab = tab
        self._startpos = None
        self._suffixes = None
        self._completing = False    # avoid recursion

    # find all words in file, sort by frequency
    def _fallback_suffix_finder(self):
        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        match = re.search(r'\w+$', before_cursor)
        if match is None:
            # can't autocomplete based on this
            return None
        prefix = match.group(0)

        # find unique words starting with the prefix
        # Tcl's regexes don't support \b or a sane way of grouping so
        # they are kind of useless for this. I guess I should implement
        # this with Tcl regexes too and check which is faster :)
        result = collections.defaultdict(int)
        for chunk in self.tab.textwidget.iter_chunks():
            for match in re.finditer(r'\b' + prefix + r'(\w+)', chunk):
                result[match.group(1)] += 1

        # if the cursor is in the middle of a word, that word must not
        # be completed, e.g. if the user types abcdef and moves the
        # cursor between c and d, we must not autocomplete to abcdefdef
        try:
            del result[re.search(r'^\w*', after_cursor).group(0)]
        except KeyError:
            pass

        return sorted(result, key=result.get, reverse=True)

    def _find_suffixes(self):
        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        if before_cursor.isspace() or not before_cursor:
            # let other plugins handle this however they want to
            return None
        if re.search(r"^\w", after_cursor) is not None:
            # don't complete in the middle of a word
            return collections.deque()

        finder = _suffix_finders.get(self.tab.filetype.name)
        if finder is None:
            return self._generic_suffix_finder()

        source = self.tab.textwidget.get("1.0", "end - 1 char")
        cursor_pos = self.tab.textwidget.index("insert")
        line, col = map(int, cursor_pos.split("."))
        return collections.deque(finder(source, line, col))

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
        return self._complete(1 if shifted else -1)

    def reset(self, *junk):
        # deleting and inserting from _complete() runs this, so this
        # must do nothing if we're currently completing
        if not self._completing:
            self._suffixes = None


def on_new_tab(event):
    # TODO: autocomplete in other kinds of tabs too?
    tab = event.widget.tabs[-1]
    if isinstance(tab, tabs.FileTab):
        completer = _AutoCompleter(tab)
        utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
        tab.textwidget.bind('<<CursorMoved>>', completer.reset, add=True)


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)
