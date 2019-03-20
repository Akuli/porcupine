"""Find/replace widget."""

# FIXME: finding 'as' or 'asa' from 'asasasasa' is broken

import re
import weakref

import teek

from porcupine import actions, get_tab_manager, images, tabs


# keys are tabs, values are Finder widgets
finders = weakref.WeakKeyDictionary()


class Finder(teek.Frame):
    """A widget for finding and replacing text.

    Use the pack geometry manager with this widget.
    """

    def __init__(self, parent, textwidget: teek.Text, **kwargs):
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

        # TODO: use the pygments theme somehow?
        self._highlight_tag = textwidget.get_tag('find_highlight')
        self._highlight_tag['foreground'] = 'black'
        self._highlight_tag['background'] = 'yellow'

        self.find_entry = self._add_entry(0, "Find:")
        find_var = self.find_entry.config['textvariable'] = teek.StringVar()
        find_var.write_trace.connect(self.highlight_all_matches)

        self.replace_entry = self._add_entry(1, "Replace with:")

        self.find_entry.bind('<Shift-Return>', self._go_to_previous_match)
        self.find_entry.bind('<Return>', self._go_to_next_match)

        # commented out because pressing tab in self.find_entry unselects the
        # text in textwidget for some reason
        # FIXME
        #self.replace_entry.bind('<Return>', self._replace_this)

        buttonframe = teek.Frame(self)
        buttonframe.grid(row=2, column=0, columnspan=4, sticky='we')

        self.previous_button = teek.Button(buttonframe, text="Previous match",
                                           command=self._go_to_previous_match)
        self.next_button = teek.Button(buttonframe, text="Next match",
                                       command=self._go_to_next_match)
        self.replace_this_button = teek.Button(
            buttonframe, text="Replace this match",
            command=self._replace_this)
        self.replace_all_button = teek.Button(
            buttonframe, text="Replace all",
            command=self._replace_all)

        self.previous_button.pack(side='left')
        self.next_button.pack(side='left')
        self.replace_this_button.pack(side='left')
        self.replace_all_button.pack(side='left')
        self._update_buttons()

        self.full_words_var = teek.BooleanVar()
        self.full_words_var.set(False)
        self.full_words_var.write_trace.connect(self.highlight_all_matches)
        self.ignore_case_var = teek.BooleanVar()
        self.ignore_case_var.set(False)
        self.ignore_case_var.write_trace.connect(self.highlight_all_matches)

        teek.Checkbutton(
            self, text="Full words only", variable=self.full_words_var).grid(
                row=0, column=3, sticky='w')
        teek.Checkbutton(
            self, text="Ignore case", variable=self.ignore_case_var).grid(
                row=1, column=3, sticky='w')

        self.statuslabel = teek.Label(self)
        self.statuslabel.grid(row=3, column=0, columnspan=4, sticky='we')

        teek.Separator(self, orient='horizontal').grid(
            row=4, column=0, columnspan=4, sticky='we')

        closebutton = teek.Label(self, cursor='hand2',
                                 image=images.get('closebutton'))
        closebutton.place(relx=1, rely=0, anchor='ne')
        closebutton.bind('<Button-1>', self.hide)

        self.grid_columns[2].config['minsize'] = 30
        self.grid_columns[3].config['weight'] = 1

        # explained in test_find_plugin.py
        textwidget.bind('<<Selection>>', self._update_buttons)

    def _add_entry(self, row, text):
        teek.Label(self, text=text).grid(row=row, column=0, sticky='w')
        entry = teek.Entry(self, width=35, font='TkFixedFont')
        entry.bind('<Escape>', self.hide)
        entry.grid(row=row, column=1, sticky='we')
        return entry

    def show(self):
        self.pack(fill='x')
        self.find_entry.focus()
        self.highlight_all_matches()

    def hide(self):
        # remove previous highlights from highlight_all_matches
        self._highlight_tag.remove()

        self.pack_forget()
        self._textwidget.focus()

    # must be called when going to another match or replacing becomes possible
    # or impossible, i.e. when _highlight_tag areas or the selection changes
    def _update_buttons(self):
        matches_something_state = (
            'normal' if self._highlight_tag.ranges() else 'disabled')

        try:
            [(start, end)] = self._textwidget.get_tag('sel').ranges()
        except ValueError:
            replace_this_state = 'disabled'
        else:   # no, elif doesn't work here
            if (start, end) in self._highlight_tag.ranges():
                replace_this_state = 'normal'
            else:
                replace_this_state = 'disabled'

        self.previous_button.config['state'] = matches_something_state
        self.next_button.config['state'] = matches_something_state
        self.replace_this_button.config['state'] = replace_this_state
        self.replace_all_button.config['state'] = matches_something_state

    def _get_matches_to_highlight(self, looking4):
        search_opts = []

        if self.ignore_case_var.get():
            search_opts.append('-nocase')

        if self.full_words_var.get():
            # tk doesn't have python-style \b, but it has \m and \M that match
            # the beginning and end of word, see re_syntax(3tcl)
            search_arg = r'\m' + looking4 + r'\M'
            search_opts.append('-regexp')
        else:
            search_arg = looking4

        start_index = '1.0'
        first_time = True

        while True:
            # searching at the beginning of a match gives that match, not
            # the next match, so we need + 1 char... unless we are looking
            # at the beginning of the file, and to avoid infinite
            # recursion, we check for that by checking if we have done it
            # before
            if first_time:
                start_index_for_search = start_index
                first_time = False
            else:
                start_index_for_search = start_index.forward(chars=1)

            # TODO: add search to teek
            args = search_opts + ['--', search_arg, start_index_for_search,
                                  self._textwidget.end]
            start_index = teek.tcl_call(
                self._textwidget.TextIndex, self._textwidget, 'search', *args)
            if start_index is None:
                # no more matches
                break
            yield start_index

    def highlight_all_matches(self, junk_var=None):
        # clear previous highlights
        self._highlight_tag.remove()

        looking4 = self.find_entry.text
        if not looking4:    # don't search for empty string
            self._update_buttons()
            self.statuslabel.config['text'] = "Type something to find."
            return
        if self.full_words_var.get():
            # check for non-wordy characters
            match = re.search(r'\W', looking4)
            if match is not None:
                self._update_buttons()
                self.statuslabel.config['text'] = (
                    "The search string can't contain "
                    '"%s" when "Full words only" is checked.' % match.group(0))
                return

        count = 0
        for start_index in self._get_matches_to_highlight(looking4):
            self._highlight_tag.add(start_index,
                                    start_index.forward(chars=len(looking4)))
            count += 1

        self._update_buttons()
        if count == 0:
            self.statuslabel.config['text'] = "Found no matches :("
        elif count == 1:
            self.statuslabel.config['text'] = "Found 1 match."
        else:
            self.statuslabel.config['text'] = "Found %d matches." % count

    def _select_range(self, start, end):
        # the tag_lower makes sure sel shows up, hiding _highlight_tag under it
        # TODO: add tag lower to teek
        teek.tcl_call(None, self._textwidget, 'tag', 'lower',
                      self._highlight_tag, 'sel')
        self._textwidget.get_tag('sel').remove()
        self._textwidget.get_tag('sel').add(start, end)
        self._textwidget.marks['insert'] = start
        self._textwidget.see(start)

    # TODO: adjust scrolling accordingly
    def _go_to_next_match(self):
        pairs = self._highlight_tag.ranges()
        if not pairs:
            # the "Next match" button is disabled in this case, but the key
            # binding of the find entry is not
            self.statuslabel.config['text'] = "No matches found!"
            return

        # find first pair that starts after the cursor
        for start, end in pairs:
            if start > self._textwidget.marks['insert']:
                self._select_range(start, end)
                break
        else:
            # reached end of file, use the first match
            self._select_range(*pairs[0])

        self.statuslabel.config['text'] = ""
        self._update_buttons()

    # see _go_to_next_match for comments
    def _go_to_previous_match(self):
        pairs = self._highlight_tag.ranges()
        if not pairs:
            self.statuslabel.config['text'] = "No matches found!"
            return

        for start, end in reversed(pairs):
            if start < self._textwidget.marks['insert']:
                self._select_range(start, end)
                break
        else:
            self._select_range(*pairs[-1])

        self.statuslabel.config['text'] = ""
        self._update_buttons()
        return

    def _replace_this(self):
        if self.replace_this_button.config['state'] == 'disabled':
            self.statuslabel.config['text'] = (
                'Click "Previous match" or "Next match" first.')
            return

        # highlighted areas must not be moved after .replace, think about what
        # happens when you replace 'asd' with 'asd'
        start, end = self._textwidget.get_tag('sel').ranges()
        self._highlight_tag.remove(start, end)
        self._update_buttons()
        self._textwidget.replace(start, end, self.replace_entry.text)

        self._textwidget.marks['insert'] = start
        self._go_to_next_match()

        left = len(self._highlight_tag.ranges())
        if left == 0:
            self.statuslabel.config['text'] = "Replaced the last match."
        elif left == 1:
            self.statuslabel.config['text'] = (
                "Replaced a match. There is 1 more match.")
        else:
            self.statuslabel.config['text'] = (
                "Replaced a match. There are %d more matches." % left)

    def _replace_all(self):
        match_ranges = self._highlight_tag.ranges()

        # must do this backwards because replacing may screw up indexes AFTER
        # the replaced place
        for start, end in reversed(match_ranges):
            self._textwidget.replace(start, end, self.replace_entry.text)
        self._highlight_tag.remove()
        self._update_buttons()

        if len(match_ranges) == 1:
            self.statuslabel.config['text'] = "Replaced 1 match."
        else:
            self.statuslabel.config['text'] = ("Replaced %d matches." %
                                               len(match_ranges))


def find():
    tab = get_tab_manager().selected_tab
    assert isinstance(tab, tabs.FileTab)
    if tab not in finders:
        finders[tab] = Finder(tab.bottom_frame, tab.textwidget)
    finders[tab].show()


def setup():
    actions.add_command("Edit/Find and Replace", find, '<Control-f>',
                        tabtypes=[tabs.FileTab])
