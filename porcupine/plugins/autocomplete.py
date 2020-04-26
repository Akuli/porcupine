import collections
import itertools
import json
import re
import tkinter.font
from tkinter import ttk

from porcupine import get_tab_manager, settings, tabs, utils

setup_before = ['tabs2spaces']      # see tabs2spaces.py
SETTINGS = settings.get_section("Autocomplete")


class AutoCompletionPopup:

    # TODO: "type to filter" sort of thing
    # TODO: display descriptions next to the thing
    # FIXME: after struct.pa<Tab>, menu shows "ck" and "ck_into" in the menu
    def __init__(self, selected_callback):
        self._selected_callback = selected_callback
        self._completion_list = None
        self._toplevel = tkinter.Toplevel()
        self._toplevel.withdraw()

        # this makes the popup have no window border and stuff. From wm(3tk):
        #
        # "Setting the override-redirect flag for a window causes it to be
        # ignored  by the window manager; among other things, this means that
        # the window will not be reparented from the root window into a
        # decorative frame and the user will not be able to manipulate the
        # window using the normal window manager mechanisms.
        self._toplevel.overrideredirect(True)

        self._treeview = ttk.Treeview(
            self._toplevel, show='tree', selectmode='browse')
        self._treeview.bind('<Motion>', self._on_mouse_move)
        self._treeview.bind('<Button-1>', self._on_click)
        self._treeview.bind('<<TreeviewSelect>>', self._on_select)

        scrollbar = ttk.Scrollbar(self._toplevel)
        self._treeview['yscrollcommand'] = scrollbar.set
        scrollbar['command'] = self._treeview.yview

        # scrollbar must be packed first, otherwise it may disappear when the
        # window is too narrow (remove overrideredirect(True) to experiment)
        scrollbar.pack(side='right', fill='y')
        self._treeview.pack(side='left', fill='both', expand=True)

        # to avoid calling selected_callback more often than needed
        self._old_selection_item_id = None

    # When tab is pressed with popups turned off in settings, this goes to a
    # state where it's completing but not showing

    def is_completing(self):
        return (self._completion_list is not None)

    def is_showing(self):
        return bool(self._toplevel.winfo_ismapped())

    def _select_item(self, item_id):
        self._treeview.selection_set(item_id)
        self._treeview.see(item_id)

    def select_previous(self):
        assert self.is_completing()
        prev_item = self._treeview.prev(self._treeview.selection())
        if prev_item:
            self._select_item(prev_item)
        else:
            self._select_item(self._treeview.get_children()[-1])

    def select_next(self):
        assert self.is_completing()
        next_item = self._treeview.next(self._treeview.selection())
        if next_item:
            self._select_item(next_item)
        else:
            self._select_item(self._treeview.get_children()[0])

    def on_page_up_down(self, event):
        if not self.is_showing():
            return None

        page_count = {'Prior': -1, 'Next': 1}[event.keysym]
        self._treeview.yview_scroll(page_count, 'pages')

        # Now it has been scrolled, but the selection hasn't moved. The
        # following code is not pretty, but tk doesn't expose the needed
        # information very much (see generic/ttk/ttkTreeview.c in source repo).

        # how tall is each element?
        self._treeview.update()     # also needed for winfo_height()
        item_height = None
        for item in self._treeview.get_children():
            bbox = self._treeview.bbox(item)
            if bbox:
                item_height = bbox[-1]
                break
        assert item_height is not None

        # how many items are visible at a time?
        item_count = self._treeview.winfo_height() // item_height
        item_count -= 1     # no idea why it's off by 1

        # find the correct item we want
        [current_item] = self._treeview.selection()
        method = {'Prior': self._treeview.prev,
                  'Next': self._treeview.next}[event.keysym]
        for lel in range(item_count):
            new_item = method(current_item)
            if not new_item:
                break
            current_item = new_item

        self._select_item(current_item)
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
        hovered_id = self._treeview.identify_row(event.y)
        if hovered_id:
            self._treeview.selection_set(hovered_id)

    def _on_click(self, event):
        self.stop_completing()

    def _on_select(self, event):
        if self.is_completing():
            [item_id] = self._treeview.selection()
            if item_id != self._old_selection_item_id:
                self._selected_callback(self._completion_list[int(item_id)])
                self._old_selection_item_id = item_id

    def start_completing(self, completion_list, x, y):
        if self.is_completing():
            # don't know when this would happen but why not handle it anyway
            self.stop_completing()

        assert completion_list
        self._completion_list = completion_list

        for index, completion in enumerate(completion_list):
            # id=str(index) is used in the rest of this class
            self._treeview.insert('', 'end', id=str(index), text=completion)

        self._treeview.selection_set('0')
        self._treeview.see('0')
        self._toplevel.geometry('250x200+%d+%d' % (x, y))

        # lazy way to implement auto completions without popup window: create
        # all the widgets but never show them :D
        if SETTINGS['show_popup']:
            self._toplevel.deiconify()

    # does nothing if not currently completing
    def stop_completing(self):
        self._toplevel.withdraw()
        self._treeview.delete(*self._treeview.get_children())
        self._completion_list = None
        self._old_selection_item_id = None


class AutoCompleter:

    def __init__(self, tab):
        self._tab = tab
        self._startpos = None
        self._id_counter = itertools.count()
        self._waiting_for_response_id = None   # None means no response matches

        # this is easy to understand but hard to explain
        # ctrl+f _can_accept_now
        self._can_accept_now = True

        self.popup = AutoCompletionPopup(self._put_suffix_to_text_widget)

    def _request_completions(self):
        the_id = next(self._id_counter)
        self._waiting_for_response_id = the_id
        self._tab.event_generate('<<AutoCompletionRequest>>', data=json.dumps({
            'id': the_id,
        }))

    def _put_suffix_to_text_widget(self, suffix):
        self._can_accept_now = False
        try:
            self._tab.textwidget.delete(self._startpos, 'insert')
            self._tab.textwidget.mark_set('insert', self._startpos)
            self._tab.textwidget.insert(self._startpos, suffix)
        finally:
            self._can_accept_now = True

    def receive_completions(self, event):
        info_dict = event.data_json()
        if info_dict['id'] != self._waiting_for_response_id:
            return
        self._waiting_for_response_id = None

        # filter out empty suffixes, they are quite confusing.
        #
        # For example, with pyls after 'import struct', type 'str' and
        # press tab. It wants to autocomplete 'str' and 'struct'
        suffixes = list(filter(bool, info_dict['suffixes']))
        if not suffixes:
            return

        relative_x, relative_y = self._tab.textwidget.bbox('insert')[:2]

        # tkinter doesn't provide a way to delete the font object, but it
        # does __del__ magic
        font_object = tkinter.font.Font(font=self._tab.textwidget['font'])
        fsize = font_object.actual('size')

        # TODO: see how pyls autocomplete the following line, jedi worked fine:
        x = self._tab.textwidget.winfo_rootx() + relative_x
        y = self._tab.textwidget.winfo_rooty() + relative_y + fsize + 10

        self.popup.start_completing(suffixes, x, y)

    def _can_complete_here(self):
        before_cursor = self._tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self._tab.textwidget.get('insert', 'insert lineend')

        return (
            # don't complete in beginning of line or with space before cursor
            re.search(r'\S$', before_cursor)
            # don't complete  in the beginning or middle of a word
            and not re.search(r'^\w', after_cursor)
        )

    def on_tab(self, event, shifted):
        if self._tab.textwidget.tag_ranges('sel'):
            # something's selected, autocompleting is not the right thing to do
            return None

        if not self.popup.is_completing():
            self._startpos = self._tab.textwidget.index('insert')
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
        if self._can_accept_now:
            self.popup.stop_completing()
            self._waiting_for_response_id = None

    def _reject(self):
        if self.popup.is_completing():
            self._put_suffix_to_text_widget('')
            self._accept()

    def on_cursor_moved(self, event):
        self._accept()

    def on_escape(self, event):
        if self.popup.is_completing():
            self._reject()
            return 'break'


def on_new_tab(event):
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        completer = AutoCompleter(tab)
        utils.bind_with_data(tab, '<<AutoCompletionResponse>>',
                             completer.receive_completions, add=True)

        utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
        tab.textwidget.bind(
            '<<CursorMoved>>', completer.on_cursor_moved, add=True)
        tab.textwidget.bind('<Escape>', completer.on_escape, add=True)
        tab.textwidget.bind(
            '<Prior>', completer.popup.on_page_up_down, add=True)
        tab.textwidget.bind(
            '<Next>', completer.popup.on_page_up_down, add=True)
        tab.textwidget.bind(
            '<Up>', completer.popup.on_arrow_key_up_down, add=True)
        tab.textwidget.bind(
            '<Down>', completer.popup.on_arrow_key_up_down, add=True)

        # stop completing when switching windows
        tab.winfo_toplevel().bind(
            '<FocusOut>', (lambda event: completer._reject()), add=True)


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
