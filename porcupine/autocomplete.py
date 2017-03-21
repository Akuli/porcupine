import collections
import re
import tkinter as tk


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
        # they are kind of useless for this. Getting the whole content
        # might seem like a bad idea, but I haven't noticed any
        # performance issues so far.
        result = set()
        content = self.textwidget.get('1.0', 'end-1c')
        for match in re.finditer(r'\b' + prefix + r'(\w+)', content):
            result.add(match.group(1))
        return collections.deque(sorted(result, key=str.casefold))

    def _complete(self, rotation):
        self._completing = True
        try:
            if self._startpos is None:
                # not completing yet
                self._startpos = self.textwidget.index('insert')
                self._suffixes = self._find_suffixes()
                self._suffixes.appendleft('')  # end of completions

            self._suffixes.rotate(rotation)
            self.textwidget.delete(self._startpos, 'insert')
            self.textwidget.mark_set('insert', self._startpos)
            self.textwidget.insert(self._startpos, self._suffixes[0])

        finally:
            self._completing = False

    def complete_previous(self):
        """Autocomplete the previous alternative.

        This should be ran when shift+tab is pressed.
        """
        self._complete(1)

    def complete_next(self):
        """Autocomplete the next alternative.

        This should be ran when tab is pressed.
        """
        self._complete(-1)

    def reset(self):
        """Forget previous completions.

        This should be called when the user keeps typing after
        completing.
        """
        # deleting and inserting text might run this if this is a
        # callback, so this must do nothing if we're currently
        # completing
        if not self._completing:
            self._suffixes = None
            self._startpos = None


if __name__ == '__main__':
    # simple test
    def on_tab(event):
        completer.complete_next()
        return 'break'

    def on_shift_tab(event):
        completer.complete_previous()
        return 'break'

    # <<Modified>> is not really correct, the real editor resets on
    # cursor movement instead
    def on_modified(event):
        text.unbind('<<Modified>>')
        text.edit_modified(False)
        text.bind('<<Modified>>', on_modified)
        completer.reset()

    root = tk.Tk()
    text = tk.Text(root)
    text.pack()

    completer = AutoCompleter(text)
    text.bind('<<Modified>>', on_modified)
    text.bind('<Tab>', on_tab)
    if root.tk.call('tk', 'windowingsystem') == 'x11':
        text.bind('<ISO_Left_Tab>', on_shift_tab)
    else:
        text.bind('<Shift-Tab>', on_shift_tab)

    root.mainloop()
