"""Find and replace text."""
# FIXME: finding 'as' or 'asa' from 'asasasasa' is broken
from __future__ import annotations

import re
import sys
import tkinter
import weakref
from functools import partial
from tkinter import ttk
from typing import Any, Iterator, List, Tuple, cast

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

from porcupine import get_tab_manager, images, menubar, tabs

finders: weakref.WeakKeyDictionary[tabs.FileTab, Finder] = weakref.WeakKeyDictionary()


class Finder(ttk.Frame):
    """A widget for finding and replacing text.

    Use the pack geometry manager with this widget.
    """

    def __init__(self, parent: tkinter.Misc, textwidget: tkinter.Text, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self._textwidget = textwidget

        # grid layout:
        #         column 0        column 1     column 2        column 3
        #     ,---------------------------------------------------------------.
        # row0|     Find:     | text entry    |       | [x] Full words only   |
        #     |---------------|---------------|-------|-----------------------|
        # row1| Replace with: | text entry    |       | [x] Ignore case       |
        #     |---------------------------------------------------------------|
        # row2| button frame, this thing contains a bunch of buttons          |
        #     |---------------------------------------------------------------|
        # row3| status label with useful-ish text                             |
        #     |---------------------------------------------------------------|
        # row4| separator                                                     |
        #     `---------------------------------------------------------------'
        #
        # note that column 2 is used just for spacing, the separator helps
        # distinguish this from e.g. status bar below this
        self.grid_columnconfigure(2, minsize=30)
        self.grid_columnconfigure(3, weight=1)

        self.full_words_var = tkinter.BooleanVar()
        self.ignore_case_var = tkinter.BooleanVar()
        find_var = tkinter.StringVar()

        self.find_entry = self._add_entry(0, "Find:")
        self.find_entry.config(textvariable=find_var)
        find_var.trace_add('write', self.highlight_all_matches)

        # because cpython gc
        cast(Any, self.find_entry).lol = find_var

        self.replace_entry = self._add_entry(1, "Replace with:")

        self.find_entry.bind('<Shift-Return>', self._go_to_previous_match, add=True)
        self.find_entry.bind('<Return>', self._go_to_next_match, add=True)

        buttonframe = ttk.Frame(self)
        buttonframe.grid(row=2, column=0, columnspan=4, sticky='we')

        self.previous_button = ttk.Button(buttonframe, text="Previous match",
                                          command=self._go_to_previous_match)
        self.next_button = ttk.Button(buttonframe, text="Next match",
                                      command=self._go_to_next_match)
        self.replace_this_button = ttk.Button(
            buttonframe, text="Replace this match", underline=len("Replace "),
            command=self._replace_this)
        self.replace_all_button = ttk.Button(
            buttonframe, text="Replace all", underline=len("Replace "),
            command=self._replace_all)

        self.previous_button.pack(side='left')
        self.next_button.pack(side='left')
        self.replace_this_button.pack(side='left')
        self.replace_all_button.pack(side='left')
        self._update_buttons()

        self.full_words_var.trace_add('write', self.highlight_all_matches)
        self.ignore_case_var.trace_add('write', self.highlight_all_matches)

        ttk.Checkbutton(
            self, text="Full words only", underline=0, variable=self.full_words_var
        ).grid(row=0, column=3, sticky='w')
        ttk.Checkbutton(
            self, text="Ignore case", underline=0, variable=self.ignore_case_var
        ).grid(row=1, column=3, sticky='w')

        self.statuslabel = ttk.Label(self)
        self.statuslabel.grid(row=3, column=0, columnspan=4, sticky='we')

        ttk.Separator(self, orient='horizontal').grid(
            row=4, column=0, columnspan=4, sticky='we')

        closebutton = ttk.Label(self, cursor='hand2')
        closebutton.place(relx=1, rely=0, anchor='ne')
        closebutton.bind('<Button-1>', self.hide, add=True)

        closebutton.config(image=images.get('closebutton'))

        # explained in test_find_plugin.py
        textwidget.bind('<<Selection>>', self._update_buttons, add=True)

        textwidget.bind('<<SettingChanged:pygments_style>>', self._config_tags, add=True)
        self._config_tags()

    def _config_tags(self, junk: object = None) -> None:
        # TODO: use more pygments theme instead of hard-coded colors?
        self._textwidget.tag_config(
            'find_highlight', foreground='black', background='yellow')
        self._textwidget.tag_config(
            'find_highlight_selected', foreground='black', background='orange')
        self._textwidget.tag_raise('find_highlight', 'sel')
        self._textwidget.tag_raise('find_highlight_selected', 'find_highlight')

    def _add_entry(self, row: int, text: str) -> ttk.Entry:
        ttk.Label(self, text=text).grid(row=row, column=0, sticky='w')
        entry = ttk.Entry(self, width=35, font='TkFixedFont')
        entry.bind('<Escape>', self.hide, add=True)
        entry.bind('<Alt-t>', self._replace_this, add=True)
        entry.bind('<Alt-a>', self._replace_all, add=True)
        entry.bind('<Alt-f>', partial(self._toggle_var, self.full_words_var), add=True)
        entry.bind('<Alt-i>', partial(self._toggle_var, self.ignore_case_var), add=True)
        entry.grid(row=row, column=1, sticky='we')
        return entry

    def _toggle_var(self, var: tkinter.BooleanVar, junk: object) -> Literal['break']:
        var.set(not var.get())
        return 'break'

    def show(self) -> None:
        try:
            selected_text = self._textwidget.get('sel.first', 'sel.last')
        except tkinter.TclError:
            selected_text = None  # A little weird, but gets the job done.

        self.pack(fill='x')

        if selected_text is None or '\n' in selected_text:
            self.find_entry.focus_set()
        else:
            # Get ready to replace this text with something else
            for entry in [self.find_entry, self.replace_entry]:
                entry.delete(0, 'end')
                entry.insert(0, selected_text)
            self.replace_entry.focus_set()

        self.highlight_all_matches()

    def hide(self, junk: object = None) -> None:
        self._textwidget.tag_remove('find_highlight', '1.0', 'end')
        self._textwidget.tag_remove('find_highlight_selected', '1.0', 'end')
        self.pack_forget()
        self._textwidget.focus_set()

    # tag_ranges returns (start1, end1, start2, end2, ...), and this thing
    # gives a list of (start, end) pairs
    def get_match_ranges(self) -> List[Tuple[str, str]]:
        starts_and_ends = list(map(str, self._textwidget.tag_ranges('find_highlight')))
        assert len(starts_and_ends) % 2 == 0
        pairs = list(zip(starts_and_ends[0::2], starts_and_ends[1::2]))
        return pairs

    # must be called when going to another match or replacing becomes possible
    # or impossible, i.e. when find_highlight areas or the selection changes
    def _update_buttons(self, junk: object = None) -> None:
        State = Literal['normal', 'disabled']
        matches_something_state: State = 'normal' if self.get_match_ranges() else 'disabled'
        replace_this_state: State

        try:
            start, end = map(str, self._textwidget.tag_ranges('sel'))
        except ValueError:
            replace_this_state = 'disabled'
        else:   # no, elif doesn't work here
            if (start, end) in self.get_match_ranges():
                replace_this_state = 'normal'
            else:
                replace_this_state = 'disabled'

        self.previous_button.config(state=matches_something_state)
        self.next_button.config(state=matches_something_state)
        self.replace_this_button.config(state=replace_this_state)
        self.replace_all_button.config(state=matches_something_state)

    def _get_matches_to_highlight(self, looking4: str) -> Iterator[str]:
        # Tkinter's .search() is slow when there are lots of tags from highlight plugin.
        # See "PERFORMANCE ISSUES" in text widget manual page
        text = self._textwidget.get('1.0', 'end - 1 char')

        if self.full_words_var.get():
            regex = r'\b' + re.escape(looking4) + r'\b|\n'
        else:
            regex = re.escape(looking4) + '|\n'
        flags = re.IGNORECASE if self.ignore_case_var.get() else 0

        lineno = 1
        for match in re.finditer(regex, text, flags):
            if match.group(0) == '\n':
                lineno += 1
            else:
                if lineno == 1:
                    column = match.start()
                else:
                    column = match.start() - text.rindex('\n', 0, match.start()) - 1
                yield f'{lineno}.{column}'

    def highlight_all_matches(self, *junk: object) -> None:
        # clear previous highlights
        self._textwidget.tag_remove('find_highlight', '1.0', 'end')

        looking4 = self.find_entry.get()
        if not looking4:    # don't search for empty string
            self._update_buttons()
            self.statuslabel.config(text="Type something to find.")
            return
        if self.full_words_var.get():
            # check for non-wordy characters
            match = re.search(r'\W', looking4)
            if match is not None:
                self._update_buttons()
                self.statuslabel.config(
                    text=f'The search string can\'t contain "{match.group(0)}" when "Full words only" is checked.'
                )
                return

        count = 0
        for start_index in self._get_matches_to_highlight(looking4):
            self._textwidget.tag_add('find_highlight', start_index, f'{start_index} + {len(looking4)} chars')
            count += 1

        self._update_buttons()
        if count == 0:
            self.statuslabel.config(text="Found no matches :(")
        elif count == 1:
            self.statuslabel.config(text="Found 1 match.")
        else:
            self.statuslabel.config(text=f"Found {count} matches.")

    def _select_match(self, start: str, end: str) -> None:
        self._textwidget.tag_remove('sel', '1.0', 'end')
        self._textwidget.tag_remove('find_highlight_selected', '1.0', 'end')
        self._textwidget.tag_add('sel', start, end)
        self._textwidget.tag_add('find_highlight_selected', start, end)
        self._textwidget.mark_set('insert', start)
        self._textwidget.see(start)

    def _go_to_next_match(self, junk: object = None) -> None:
        pairs = self.get_match_ranges()
        if not pairs:
            # the "Next match" button is disabled in this case, but the key
            # binding of the find entry is not
            self.statuslabel.config(text="No matches found!")
            return

        # find first pair that starts after the cursor
        for start, end in pairs:
            if self._textwidget.compare(start, '>', 'insert'):
                self._select_match(start, end)
                break
        else:
            # reached end of file, use the first match
            self._select_match(*pairs[0])

        self.statuslabel.config(text="")
        self._update_buttons()

    # see _go_to_next_match for comments
    def _go_to_previous_match(self, junk: object = None) -> None:
        pairs = self.get_match_ranges()
        if not pairs:
            self.statuslabel.config(text="No matches found!")
            return

        for start, end in reversed(pairs):
            if self._textwidget.compare(start, '<', 'insert'):
                self._select_match(start, end)
                break
        else:
            self._select_match(*pairs[-1])

        self.statuslabel.config(text="")
        self._update_buttons()
        return

    def _replace_this(self, junk: object = None) -> None:
        if str(self.replace_this_button.cget('state')) == 'disabled':
            self.statuslabel.config(text='Click "Previous match" or "Next match" first.')
            return

        # highlighted areas must not be moved after .replace, think about what
        # happens when you replace 'asd' with 'asd'
        start, end = self._textwidget.tag_ranges('sel')
        self._textwidget.tag_remove('find_highlight', start, end)
        self._update_buttons()
        self._textwidget.replace(start, end, self.replace_entry.get())

        self._textwidget.mark_set('insert', start)
        self._go_to_next_match()

        left = len(self.get_match_ranges())
        if left == 0:
            self.statuslabel.config(text="Replaced the last match.")
        elif left == 1:
            self.statuslabel.config(text="Replaced a match. There is 1 more match.")
        else:
            self.statuslabel.config(text=f"Replaced a match. There are {left} more matches.")

    def _replace_all(self, junk: object = None) -> None:
        match_ranges = self.get_match_ranges()

        # must do this backwards because replacing may screw up indexes AFTER
        # the replaced place
        for start, end in reversed(match_ranges):
            self._textwidget.replace(start, end, self.replace_entry.get())
        self._textwidget.tag_remove('find_highlight', '1.0', 'end')
        self._update_buttons()

        if len(match_ranges) == 1:
            self.statuslabel.config(text="Replaced 1 match.")
        else:
            self.statuslabel.config(text=f"Replaced {len(match_ranges)} matches.")


def find() -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    if tab not in finders:
        finders[tab] = Finder(tab.bottom_frame, tab.textwidget)
    finders[tab].show()


def setup() -> None:
    menubar.get_menu("Edit").add_command(label="Find and Replace", command=find)
    menubar.set_enabled_based_on_tab("Edit/Find and Replace", (lambda tab: isinstance(tab, tabs.FileTab)))
