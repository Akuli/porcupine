import collections
import re

from porcupine import get_tab_manager, tabs, utils


setup_before = ['tabs2spaces']      # see tabs2spaces.py


class _AutoCompleter:

    def __init__(self, tab):
        self.tab = tab
        self._startpos = None
        self._suffixes = None
        self._completing = False    # avoid recursion

    def _find_suffixes(self):
        if self.tab.completer is None:
            # let other plugins handle this however they want to
            return None

        before_cursor = self.tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self.tab.textwidget.get('insert', 'insert lineend')

        if re.search(r'\S$', before_cursor) is None:
            # let other plugins handle this however they want to
            return None
        if re.search(r'^\w', after_cursor) is not None:
            # don't complete in the middle of a word
            return []

        return self.tab.completer(self.tab)

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
