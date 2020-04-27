import collections
import itertools
import json
import re
import tkinter.font
from tkinter import ttk

from porcupine import get_tab_manager, settings, tabs, utils

setup_before = ['tabs2spaces']      # see tabs2spaces.py
SETTINGS = settings.get_section("Autocomplete")


def pack_with_scrollbar(widget):
    scrollbar = ttk.Scrollbar(widget.master)
    widget['yscrollcommand'] = scrollbar.set
    scrollbar['command'] = widget.yview

    # scroll bar must be packed first to make sure that it's always displayed
    scrollbar.pack(side='right', fill='y')
    widget.pack(side='left', fill='both', expand=True)
    return scrollbar


def add_resize_handle(toplevel):
    between_mouse_and_window_corner = [0, 0]

    # Doing this only in the beginning of resize ensures that if it's off by 1
    # for whatever reason, then it will only ever be off by 1 pixel, rather
    # than off by 1 pixel MORE for each resize event. If I put this to
    # do_resize() instead, then for some reason, the window doesn't resize
    # at all.
    def begin_resize(event):
        between_mouse_and_window_corner[:] = [
            event.widget.winfo_width() - event.x,
            event.widget.winfo_height() - event.y
        ]

    def do_resize(event):
        x_offset, y_offset = between_mouse_and_window_corner
        width = event.x_root - toplevel.winfo_rootx() + x_offset
        height = event.y_root - toplevel.winfo_rooty() + y_offset

        if width >= 0 and height >= 0:
            toplevel.geometry('%dx%d' % (width, height))

    handle = ttk.Label(toplevel, text="⇲")      # unicode awesomeness
    handle.bind('<Button-1>', begin_resize)
    handle.bind('<Button1-Motion>', do_resize)
    handle.place(relx=1, rely=1, anchor='se')
    return handle


class AutoCompletionPopup:

    # FIXME: io.string<Tab> completes to io.stringIO, first s should be S
    # FIXME: closing porcupine while completion popup is visible
    def __init__(self, selected_callback):
        self._selected_callback = selected_callback
        self.completion_list = None

        # to avoid calling selected_callback more often than needed
        self._old_selection_item_id = None

        self._toplevel = tkinter.Toplevel()
        self._toplevel.withdraw()
        self._toplevel.overrideredirect(True)

        # from tkinter/ttk.py:
        #
        #   PanedWindow = Panedwindow # tkinter name compatibility
        #
        # I'm using Panedwindow here in case the PanedWindow alias is deleted
        # in a future version of python.
        self._panedwindow = ttk.Panedwindow(
            self._toplevel, orient='horizontal')
        self._panedwindow.pack(fill='both', expand=True)

        left_pane = ttk.Frame(self._panedwindow)
        right_pane = ttk.Frame(self._panedwindow)
        self._panedwindow.add(left_pane)
        self._panedwindow.add(right_pane)

        self.treeview = ttk.Treeview(
            left_pane, show='tree', selectmode='browse')
        self.treeview.bind('<Motion>', self._on_mouse_move)
        self.treeview.bind('<<TreeviewSelect>>', self._on_select)
        self._left_scrollbar = pack_with_scrollbar(self.treeview)

        self._doc_text = utils.create_passive_text_widget(
            right_pane, width=50, height=15, wrap='word')
        self._right_scrollbar = pack_with_scrollbar(self._doc_text)

        self._resize_handle = add_resize_handle(self._toplevel)
        self._toplevel.bind('<Configure>', self._on_anything_resized)

        # turns out to be best to get the initial divider position now.
        # Otherwise it tends to get written to SETTINGS before it's read for
        # the first time.
        self._initial_divider_pos = SETTINGS['popup_divider_pos']

    def _on_anything_resized(self, event):
        # When the separator is dragged all the way to left or the popup is
        # resized to be narrow enough, the right scrollbar is no longer mapped
        # (i.e. visible) but the left scrollbar must get out of the way of the
        # resize handle. Otherwise the left scrollbar can go all the way to the
        # bottom of the popup, but the right scrollbar must make room.
        handle_height = self._resize_handle.winfo_height()
        if self._right_scrollbar.winfo_ismapped():
            self._left_scrollbar.pack(pady=[0, 0])
            self._right_scrollbar.pack(pady=[0, handle_height])
        else:
            self._left_scrollbar.pack(pady=[0, handle_height])
            self._right_scrollbar.pack(pady=[0, 0])

        # winfo doesn't work very well when the widgets are not actually
        # visible. Also, better to check _panedwindow, because for a tiny
        # moment, the window is visible but _panedwindow isn't.
        if self._panedwindow.winfo_ismapped():
            SETTINGS['popup_window_width'] = self._toplevel.winfo_width()
            SETTINGS['popup_window_height'] = self._toplevel.winfo_height()
            SETTINGS['popup_divider_pos'] = self._panedwindow.sashpos(0)

    # When tab is pressed with popups turned off in settings, this goes to a
    # state where it's completing but not showing.

    def is_completing(self):
        return (self.completion_list is not None)

    def is_showing(self):
        return bool(self._toplevel.winfo_ismapped())

    def _select_item(self, item_id):
        self.treeview.selection_set(item_id)
        self.treeview.see(item_id)

    def start_completing(self, completion_list, popup_xy):
        if self.is_completing():
            self.stop_completing(withdraw=False)

        assert completion_list
        assert '' not in (compl['suffix'] for compl in completion_list)
        self.completion_list = completion_list

        for index, completion in enumerate(completion_list):
            # id=str(index) is used in the rest of this class
            self.treeview.insert('', 'end', id=str(index),
                                 text=completion['display_text'])

        self._select_item('0')
        if popup_xy is not None:
            x, y = popup_xy
            self._toplevel.geometry('%dx%d+%d+%d' % (
                SETTINGS['popup_window_width'],
                SETTINGS['popup_window_height'],
                x, y))

        # lazy way to implement auto completion without popup window: create
        # all the widgets but never show them :D
        if SETTINGS['show_popup']:
            self._toplevel.deiconify()

        # don't know why after_idle is needed, but it is
        self._panedwindow.after_idle(
            lambda: self._panedwindow.sashpos(0, self._initial_divider_pos))

    # does nothing if not currently completing
    def stop_completing(self, *, withdraw=True):
        if withdraw:
            self._toplevel.withdraw()

        self.treeview.delete(*self.treeview.get_children())
        self.completion_list = None
        self._old_selection_item_id = None

    def select_previous(self):
        assert self.is_completing()
        prev_item = self.treeview.prev(self.treeview.selection())
        if prev_item:
            self._select_item(prev_item)
        else:
            self._select_item(self.treeview.get_children()[-1])

    def select_next(self):
        assert self.is_completing()
        next_item = self.treeview.next(self.treeview.selection())
        if next_item:
            self._select_item(next_item)
        else:
            self._select_item(self.treeview.get_children()[0])

    def on_page_up_down(self, event):
        if not self.is_showing():
            return None

        page_count = {'Prior': -1, 'Next': 1}[event.keysym]
        self._doc_text.yview_scroll(page_count, 'pages')
        return 'break'

    def on_arrow_key_up_down(self, event):
        if not self.is_showing():
            return None

        method = {'Up': self.select_previous,
                  'Down': self.select_next}[event.keysym]
        method()
        return 'break'

    def _on_mouse_move(self, event):
        # ttk_treeview(3tk) says that 'identify row' is "Obsolescent synonym
        # for pathname identify item", but tkinter doesn't have identify_item
        hovered_id = self.treeview.identify_row(event.y)
        if hovered_id:
            self.treeview.selection_set(hovered_id)

    def _on_select(self, event):
        if self.is_completing():
            [item_id] = self.treeview.selection()
            if item_id != self._old_selection_item_id:
                self._old_selection_item_id = item_id
                completion = self.completion_list[int(item_id)]

                self._selected_callback(completion)
                self._doc_text['state'] = 'normal'
                self._doc_text.delete('1.0', 'end')
                self._doc_text.insert('1.0', completion['documentation'])


# yes, i know that i shouldn't do math with rgb colors
def mix_colors(color1, color2):
    widget = get_tab_manager()      # any widget would do for this
    r, g, b = (
        sum(pair) // 2     # average
        for pair in zip(widget.winfo_rgb(color1), widget.winfo_rgb(color2))
    )

    # tk uses 16-bit colors for some reason, converting to 8-bit
    return '#%02x%02x%02x' % (r >> 8, g >> 8, b >> 8)


def filter_completions(completions, filtering_prefix):
    return [
        dict(collections.ChainMap(
            # override suffix with a chopped version
            {'suffix': completion['suffix'][len(filtering_prefix):]},
            completion,
        ))
        for completion in completions

        # pyls compares case-insensitively here, match its behaviour
        # TODO: lsp supports filterText which is likely meant for this?
        if completion['suffix'].lower().startswith(filtering_prefix.lower())
        and len(completion['suffix']) > len(filtering_prefix)
    ]


class AutoCompleter:

    def __init__(self, tab):
        self._tab = tab
        self._endpos = None
        self._id_counter = itertools.count()
        self._waiting_for_response_id = None   # None means no response matches
        self._putting_to_text_widget = False
        self.popup = AutoCompletionPopup(
            lambda completion: self._put_to_text_widget(completion['suffix']))

        # Because text can be typed while autocompletion request is being
        # processed. The goal is that typing 'foo.<tab>a' and 'foo.a<tab>'
        # should do the same thing.
        self._filter_queue = ''

    def _request_completions(self):
        self._endpos = self._tab.textwidget.index('insert')

        the_id = next(self._id_counter)
        self._waiting_for_response_id = the_id
        self._filter_queue = ''

        self._tab.event_generate('<<AutoCompletionRequest>>', data=json.dumps({
            'id': the_id,
            # use this cursor pos in e.g. lsp.py, because while processing the
            # completion request, user might type more
            'cursor_pos': self._tab.textwidget.index('insert'),
        }))

    def _put_to_text_widget(self, suffix):
        self._tab.textwidget['autoseparators'] = False
        self._putting_to_text_widget = True

        try:
            old_cursor_pos = self._tab.textwidget.index('insert')
            self._tab.textwidget.delete('insert', self._endpos)
            self._tab.textwidget.insert('insert', suffix, 'autocompletion')
            self._endpos = self._tab.textwidget.index('insert')
            self._tab.textwidget.mark_set('insert', old_cursor_pos)
        finally:
            self._tab.textwidget['autoseparators'] = True
            self._putting_to_text_widget = False

    def receive_completions(self, event):
        info_dict = event.data_json()
        if info_dict['id'] != self._waiting_for_response_id:
            return
        self._waiting_for_response_id = None

        completions = filter_completions(
            info_dict['completions'], self._filter_queue)
        self._filter_queue = ''
        if not completions:
            return

        relative_x, relative_y = self._tab.textwidget.bbox('insert')[:2]

        # tkinter doesn't provide a way to delete the font object, but it
        # does __del__ magic
        font_object = tkinter.font.Font(font=self._tab.textwidget['font'])
        fsize = font_object.actual('size')

        # TODO: see how pyls autocomplete the following line, jedi worked fine:
        x = self._tab.textwidget.winfo_rootx() + relative_x
        y = self._tab.textwidget.winfo_rooty() + relative_y + fsize + 10

        self.popup.start_completing(completions, (x, y))

    # returns None if this isn't a place where it's good to autocomplete
    def _can_complete_here(self):
        before_cursor = self._tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self._tab.textwidget.get('insert', 'insert lineend')

        # don't complete in beginning of line or with space before cursor
        if not re.search(r'\S$', before_cursor):
            return False

        # don't complete in the beginning or middle of a word
        if re.search(r'^\w', after_cursor):
            return False

        return True

    def on_tab(self, event, shifted):
        if self._tab.textwidget.tag_ranges('sel'):
            # something's selected, autocompleting is not the right thing to do
            return None

        if not self.popup.is_completing():
            if not self._can_complete_here():
                # let tabs2spaces and other plugins handle it
                return None

            self._request_completions()
            return 'break'

        if shifted:
            self.popup.select_previous()
        else:
            self.popup.select_next()
        return 'break'

    def _accept(self):
        if not self.popup.is_completing():
            return

        self.popup.stop_completing()
        self._tab.textwidget.tag_remove('autocompletion', '1.0', 'end')
        self._tab.textwidget.mark_set('insert', self._endpos)
        self._waiting_for_response_id = None
        self._tab.textwidget.edit_separator()

    def _reject(self):
        if self.popup.is_completing():
            self._put_to_text_widget('')
            self._accept()

    def on_any_key(self, event):
        its_just_a_letter = (len(event.char) == 1 and event.char.isprintable())

        if not self.popup.is_completing():
            if event.char in self._tab.filetype.autocomplete_chars:
                def do_request():
                    if ((not self.popup.is_completing())
                            and self._can_complete_here()):
                        self._request_completions()

                # Tiny delay added for things like langserver, to make sure
                # that langserver's change events get sent before completions
                # are requested.
                self._tab.after(10, do_request)

                self._filter_queue = ''
                self._waiting_for_response_id = None
                return None

            if self._waiting_for_response_id is not None:
                if its_just_a_letter:
                    self._filter_queue += event.char
                else:
                    self._filter_queue = ''
                    self._waiting_for_response_id = None

            return None

        if self._putting_to_text_widget:
            return None

        if not its_just_a_letter:
            # allow typing capital letters to filter through completions.
            # On my system, the keysym is 'Shift_L' or 'Shift_R'.
            if not event.keysym.startswith('Shift'):
                self._reject()

            return None

        # user typed a letter, let's filter through the list
        completions = filter_completions(
            self.popup.completion_list, event.char)
        if not completions:
            self._reject()
            return None

        self._put_to_text_widget('')
        self.popup.stop_completing(withdraw=False)
        self._tab.textwidget.insert('insert', event.char)
        self.popup.start_completing(completions, None)
        return 'break'

    def on_enter(self, event):
        if not self.popup.is_completing():
            return None

        self._accept()
        return 'break'

    def on_escape(self, event):
        if self.popup.is_completing():
            self._reject()
            return 'break'


def on_new_tab(event):
    tab = event.data_widget()
    if not isinstance(tab, tabs.FileTab):
        return

    tab.textwidget.tag_config('autocompletion', foreground=mix_colors(
        tab.textwidget['fg'], tab.textwidget['bg']))

    completer = AutoCompleter(tab)
    utils.bind_with_data(tab, '<<AutoCompletionResponse>>',
                         completer.receive_completions, add=True)

    # no idea why backspace has to be bound separately
    utils.bind_with_data(
        tab.textwidget, '<Key>', completer.on_any_key, add=True)
    tab.textwidget.bind('<BackSpace>', completer.on_any_key, add=True)

    utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
    tab.textwidget.bind('<Return>', completer.on_enter, add=True)
    tab.textwidget.bind('<Escape>', completer.on_escape, add=True)
    tab.textwidget.bind(
        '<Prior>', completer.popup.on_page_up_down, add=True)
    tab.textwidget.bind(
        '<Next>', completer.popup.on_page_up_down, add=True)
    tab.textwidget.bind(
        '<Up>', completer.popup.on_arrow_key_up_down, add=True)
    tab.textwidget.bind(
        '<Down>', completer.popup.on_arrow_key_up_down, add=True)
    completer.popup.treeview.bind(
        '<Button-1>', (lambda event: completer._accept()), add=True)

    # avoid weird corner cases
    tab.winfo_toplevel().bind(
        '<FocusOut>', (lambda event: completer._reject()), add=True)
    tab.textwidget.bind(
        # any mouse button
        '<Button>', (lambda event: completer._reject()), add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)

    SETTINGS.add_label(
        # TODO: add documentation for setting up langserver and a link to
        #       that here
        "If autocompletion isn't working, make sure that you have langserver "
        "(or something else that works with the autocomplete plugin) set up "
        "correctly.")

    SETTINGS.add_option('show_popup', True)
    SETTINGS.add_checkbutton(
        'show_popup', "Show a popup window when autocompleting")

    SETTINGS.add_option('popup_window_width', 500, reset=False)
    SETTINGS.add_option('popup_window_height', 200, reset=False)
    SETTINGS.add_option('popup_divider_pos', 200, reset=False)
