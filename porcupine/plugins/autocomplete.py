# TODO: document this module's simple register_completer() api
import collections
import re

from porcupine import get_tab_manager, tabs, utils

__all__ = ['register_completer']
setup_before = ['tabs2spaces']      # see tabs2spaces.py

_completers = {}


def register_completer(filetype_name, function):
    """Add a syntax completer for a specific filetype.

    Use like this::

        from porcupine.plugins import autocomplete

        def java_completer(tab):
            # Do whatever you need to do with the text widget. For example:
            full_content = tab.textwidget.get('1.0', 'end - 1 char')
            cursor_line, cursor_col = map(int, tab.textwidget.index('insert')\
.split('.'))

            # This should return an iterable of things that can be inserted
            # after the current cursor position, or e.g. [] for no completions.

        def setup():
            autocomplete.register_completer("Java", java_completer)

    The ``tab`` argument to *function* is a :class:`porcupine.tabs.Filetab`.

    The *filetype_name* should be a key of
    :data:`porcupine.filetypes.filetypes`. Registering multiple completers
    for the same *filetype_name* overrides previous registrations.
    """
    _completers[filetype_name] = function


def _fallback_completer(tab):
    """Find all words in file, sorted by frequency."""
    before_cursor = tab.textwidget.get('insert linestart', 'insert')
    after_cursor = tab.textwidget.get('insert', 'insert lineend')

    match = re.search(r'\w+$', before_cursor)
    if match is None:
        # can't autocomplete based on this
        return None
    prefix = match.group(0)

    # find unique words starting with the prefix
    # Tcl's regexes don't support \b or a sane way of grouping so
    # they are kind of useless for this. I guess I should implement
    # this with Tcl regexes too and check which is faster :)
    result = collections.Counter()
    for chunk in tab.textwidget.iter_chunks():
        result.update(re.findall(r'\b' + prefix + r'(\w+)', chunk))

    # if the cursor is in the middle of a word, that word must not
    # be completed, e.g. if the user types abcdef and moves the
    # cursor between c and d, we must not autocomplete to abcdefdef
    try:
        del result[re.search(r'^\w*', after_cursor).group(0)]
    except KeyError:
        pass

    return sorted(result, key=result.get, reverse=True)


class _AutoCompleter:

    def __init__(self, tab):
        self.tab = tab
        self._startpos = None
        self._suffixes = None
        self._completing = False    # avoid recursion

    def _find_suffixes(self):
        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        if re.search(r'\S$', before_cursor) is None:
            # let other plugins handle this however they want to
            return None
        if re.search(r'^\w', after_cursor) is not None:
            # don't complete in the middle of a word
            return []

        completer = _completers.get(self.tab.filetype.name,
                                    _fallback_completer)
        return completer(self.tab)

    def _complete(self, rotation):
        self._completing = True

        if self._suffixes is None:
            suffixes = self._find_suffixes()
            if suffixes is None:
                # no completable characters before the cursor, just give
                # up and allow doing something else on this tab press
                return None

            self._startpos = self.tab.textwidget.index('insert')
            self._suffixes = collections.deque(suffixes)
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
    tab = event.data_widget
    if isinstance(tab, tabs.FileTab):
        completer = _AutoCompleter(tab)
        utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
        tab.textwidget.bind('<<CursorMoved>>', completer.reset, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
