import collections
import re

from porcupine import get_tab_manager, tabs, utils


setup_before = ['tabs2spaces']      # see tabs2spaces.py


class _AutoCompleter:

    def __init__(self, tab):
        self.tab = tab
        self._replacements = None   # deque of (start, end, text) tuples
        self._original_line = None  # before applying the latest replacement
        self._completing = False    # avoid recursion

    def _find_replacements(self):
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

    def _on_same_line(self, index1, index2):
        index1 = self.tab.textwidget.index(index1)
        index2 = self.tab.textwidget.index(index2)
        return (index1.split('.')[0] == index2.split('.')[0])

    def _complete(self, rotation):
        self._completing = True

        if self._replacements is None:
            replacements = self._find_replacements()
            if replacements is None:
                # no completable characters before the cursor, just give
                # up and allow doing something else on this tab press
                return None

            self._replacements = collections.deque(replacements)

            # end of completions
            cursor_pos = self.tab.textwidget.index('insert')
            self._replacements.appendleft((cursor_pos, cursor_pos, ''))

            # make sure they are all on 1 line because otherwise stuff breaks
            for start, end, text in self._replacements:
                assert self._on_same_line(start, cursor_pos)
                assert self._on_same_line(end, cursor_pos)

            # the 1 line thing makes sure that this is enough
            self._original_line = self.tab.textwidget.get(
                'insert linestart', 'insert lineend')

        self._replacements.rotate(rotation)
        start, end, text = self._replacements[0]
        start = self.tab.textwidget.index(start)   # makes sure its 'x.y'

        line_start = start.split('.')[0] + '.0'
        self.tab.textwidget.delete(line_start, line_start + ' lineend')
        self.tab.textwidget.insert(line_start, self._original_line)
        self.tab.textwidget.delete(start, end)
        self.tab.textwidget.insert(start, text)

        new_cursor_column = int(start.split('.')[1]) + len(text)
        self.tab.textwidget.mark_set(
            'insert', '%s + %d chars' % (line_start, new_cursor_column))

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
            self._replacements = None


def on_new_tab(event):
    # TODO: autocomplete in other kinds of tabs too?
    tab = event.data_widget
    if isinstance(tab, tabs.FileTab):
        completer = _AutoCompleter(tab)
        utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
        tab.textwidget.bind('<<CursorMoved>>', completer.reset, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
