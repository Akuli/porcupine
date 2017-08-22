"""Find/replace widget."""
import re
import tkinter as tk
import weakref

import porcupine
from porcupine import utils

find_widgets = weakref.WeakKeyDictionary()


class Finder(tk.Frame):
    """A widget for finding and replacing text.

    Use the pack geometry manager with this widget.
    """

    def __init__(self, parent, textwidget, **kwargs):
        super().__init__(parent, **kwargs)

        self._last_pattern = None
        self._matches = None

        self.grid_columnconfigure(1, weight=1)
        self._textwidget = textwidget

        entrygrid = tk.Frame(self)
        entrygrid.grid(row=0, column=0)
        self._find_entry = self._add_entry(entrygrid, 0, "Find:", self.find)
        self._replace_entry = self._add_entry(entrygrid, 1, "Replace with:")

        buttonframe = tk.Frame(self)
        buttonframe.grid(row=1, column=0, sticky='we')
        buttons = [
            ("Find", self.find),
            ("Replace", self.replace),
            ("Replace and find", self.replace_and_find),
            ("Replace all", self.replace_all),
        ]
        for text, command in buttons:
            button = tk.Button(buttonframe, text=text, command=command)
            button.pack(side='left', fill='x', expand=True)

        self._full_words_var = tk.BooleanVar()
        checkbox = utils.Checkbox(self, text="Full words only",
                                  variable=self._full_words_var)
        checkbox.grid(row=0, column=1, sticky='nw')

        self._statuslabel = tk.Label(self)
        self._statuslabel.grid(row=1, column=1, columnspan=2, sticky='nswe')

        closebutton = tk.Label(self, image='img_closebutton')
        closebutton.grid(row=0, column=2, sticky='ne')
        closebutton.bind('<Button-1>', lambda event: self.pack_forget())

    def _add_entry(self, frame, row, text, callback=None):
        tk.Label(frame, text=text).grid(row=row, column=0)
        entry = tk.Entry(frame, width=35, font='TkFixedFont')
        entry.bind('<Escape>', lambda event: self.pack_forget())
        if callback is not None:
            entry.bind('<Return>', lambda event: callback())
        entry.grid(row=row, column=1, sticky='we')
        return entry

    # reset this when showing
    def pack(self, *args, **kwargs):
        self.reset()
        super().pack(*args, **kwargs)

    def _next_match(self):
        what = self._find_entry.get()
        full_words = self._full_words_var.get()

        if not what:
            self._statuslabel['text'] = "Cannot find an emptiness!"
            return None
        if full_words:
            regexp = r"\b%s\b" % re.escape(what)
        else:
            regexp = re.escape(what)

        if self._last_pattern != regexp:
            matches = []
            for y, line in enumerate(self._textwidget.iter_lines()):
                for match in re.finditer(regexp, line):
                    matches.append((y + 1, match.start(),
                                    match.end() - match.start()))

            self._last_pattern = regexp
            self._matches = iter(matches)

        return next(self._matches, None)

    def find(self):
        match = self._next_match()

        if match is not None:
            self._statuslabel['text'] = ''

            line, col, match_len = match

            start = "%d.%d" % (line, col)
            end = "%s + %d chars" % (start, match_len)

            self._textwidget.tag_remove('sel', '1.0', 'end')
            self._textwidget.tag_add('sel', start, end)
            self._textwidget.mark_set('insert', start)
            self._textwidget.see(start)
            return True
        else:
            self._statuslabel['text'] = "I can't find it :("
            return False

    def replace(self):
        find_text = self._find_entry.get()
        if not find_text:
            self._statuslabel['text'] = "Cannot replace an emptiness!"
            return
        elif self._last_pattern is None:
            self._statuslabel['text'] = "Press find first!"
            return

        start, end = self._textwidget.tag_ranges('sel')
        if self._textwidget.index(start) == self._textwidget.index(end):
            # empty area selected
            self._statuslabel['text'] = "Nothing selected!"
            return

        if not re.match(self._last_pattern, self._textwidget.get(start, end)):
            # wrong text selected
            self._statuslabel['text'] = "Wrong text selected!"

        replace_text = self._replace_entry.get()
        self._textwidget.delete(start, end)
        self._textwidget.insert(start, replace_text)
        new_end = '%s + %d chars' % (start, len(replace_text))
        self._textwidget.tag_add('sel', start, new_end)

    def replace_and_find(self):
        self.replace()
        self.find()

    def replace_all(self):
        old_cursor_pos = self._textwidget.index("insert")

        count = 0
        while self.find():
            self.replace()
            count += 1

        self._textwidget.tag_remove('sel', '1.0', 'end')
        self._textwidget.mark_set("insert", old_cursor_pos)

        if count == 1:
            self._statuslabel['text'] = "Replaced 1 occurence."
        else:
            self._statuslabel['text'] = "Replaced %d occurences." % count

    def reset(self):
        self._statuslabel['text'] = ''
        self._find_entry.focus()
        self._last_pattern = None
        self._matches = None


def find():
    current_tab = porcupine.get_tab_manager().current_tab
    find_widgets[current_tab].pack(fill='x')


def on_new_tab(event):
    tab = event.widget.current_tab

    find_widgets[tab] = Finder(tab, tab.textwidget)
    tab.textwidget.bind("<<ContentChanged>>",
                        lambda _: find_widgets[tab].reset(),
                        add=True)


def on_tab_changed(event):
    current_tab = event.widget.current_tab
    if current_tab in find_widgets:
        find_widgets[current_tab].reset()


def setup():
    porcupine.add_action(find,
                         "Edit/Find and Replace", ("Ctrl+F", '<Control-f>'),
                         tabtypes=[porcupine.tabs.FileTab])
    tab_manager = porcupine.get_tab_manager()
    tab_manager.bind("<<NewTab>>", on_new_tab, add=True)
    tab_manager.bind("<<CurrentTabChanged>>", on_tab_changed, add=True)
