"""Find/replace widget."""
import re
import sys
import tkinter as tk
from tkinter import ttk
import weakref

from porcupine import actions, get_tab_manager, images, tabs, utils


# keys are tabs, values are Finder widgets
finders = weakref.WeakKeyDictionary()


class Finder(ttk.Frame):
    """A widget for finding and replacing text.

    Use the pack geometry manager with this widget.
    """

    def __init__(self, parent, textwidget, **kwargs):
        super().__init__(parent, **kwargs)

        self.grid_columnconfigure(1, weight=1)
        self._textwidget = textwidget

        entrygrid = ttk.Frame(self)
        entrygrid.grid(row=0, column=0)

        self.find_entry = self._add_entry(entrygrid, 0, "Find:")
        find_var = self.find_entry['textvariable'] = tk.StringVar()
        find_var.trace('w', self.highlight_all_matches)
        self.find_entry.lol = find_var     # because cpython gc

        #self._replace_entry = self._add_entry(entrygrid, 1, "Replace with:")

        buttonframe = ttk.Frame(self)
        buttonframe.grid(row=1, column=0, sticky='we')
        buttons = [
        ]
        for text, command in buttons:
            button = ttk.Button(buttonframe, text=text, command=command)
            button.pack(side='left', fill='x', expand=True)

        #self._full_words_var = tk.BooleanVar()
        #checkbox = ttk.Checkbutton(self, text="Full words only",
        #                           variable=self._full_words_var)
        #checkbox.grid(row=0, column=1, sticky='nw')

        self.statuslabel = ttk.Label(self)
        self.statuslabel.grid(row=1, column=1, columnspan=2, sticky='nswe')

        # see set_status
        self._orig_statuslabel_color = self.statuslabel['foreground']

        closebutton = ttk.Label(self, cursor='hand2')
        closebutton.grid(row=0, column=2, sticky='ne')
        closebutton.bind('<Button-1>', self.hide)

        # TODO: figure out why images don't work in tests
        if 'pytest' not in sys.modules:     # pragma: no cover
            closebutton['image'] = images.get('closebutton')

        # TODO: use the pygments theme somehow?
        textwidget.tag_config('find_match',
                              foreground='black', background='yellow')

    def _add_entry(self, frame, row, text):
        ttk.Label(frame, text=text).grid(row=row, column=0)
        entry = ttk.Entry(frame, width=35, font='TkFixedFont')
        entry.bind('<Escape>', self.hide)
        entry.grid(row=row, column=1, sticky='we')
        return entry

    def set_status(self, text, *, error=False):
        self.statuslabel['text'] = text
        self.statuslabel['foreground'] = (
            'red' if error else self._orig_statuslabel_color)

    def show(self):
        self.pack(fill='x')
        self.find_entry.focus_set()
        self.highlight_all_matches()

    def hide(self, junk_event=None):
        # remove previous highlights from highlight_all_matches
        self._textwidget.tag_remove('find_match', '1.0', 'end')

        self.pack_forget()
        self._textwidget.focus_set()

    def highlight_all_matches(self, *junk):
        # clear previous highlights
        self._textwidget.tag_remove('find_match', '1.0', 'end')

        count = 0
        looking4 = self.find_entry.get()
        if looking4:        # don't search for empty string
            start_index = '1.0'
            while True:
                # searching at the beginning of a match gives that match, not
                # the next match, so we need + 1 char... unless we are looking
                # at the beginning of the file, and to avoid infinite
                # recursion, we haven't done it before
                if start_index == '1.0' and count == 0:
                    search_arg = start_index
                else:
                    search_arg = '%s + 1 char' % start_index

                start_index = self._textwidget.search(
                    looking4, search_arg, 'end')
                if not start_index:
                    # no more matches
                    break

                self._textwidget.tag_add(
                    'find_match', start_index,
                    '%s + %d chars' % (start_index, len(looking4)))
                count += 1

        if count == 1:
            self.statuslabel['text'] = "Found 1 match."
        else:
            self.statuslabel['text'] = "Found %d matches." % count


def find():
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    if tab not in finders:
        finders[tab] = Finder(tab.bottom_frame, tab.textwidget)
    finders[tab].show()


def setup():
    actions.add_command("Edit/Find and Replace", find, '<Control-f>',
                        tabtypes=[tabs.FileTab])
