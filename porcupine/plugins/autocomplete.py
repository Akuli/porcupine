# TODO: when no langserver, fallback autocompleting with "all words in file"
#       type thing

import dataclasses
import itertools
import re
import tkinter
from tkinter import ttk
import typing

from porcupine import get_tab_manager, settings, tabs, utils

setup_before = ['tabs2spaces']      # see tabs2spaces.py
_SETTINGS = settings.get_section("Autocomplete")


@dataclasses.dataclass
class Completion:
    display_text: str
    replace_start: str
    replace_end: str
    replace_text: str
    filter_text: str
    documentation: str


def _pack_with_scrollbar(
        widget: typing.Union[ttk.Treeview, tkinter.Text]) -> ttk.Scrollbar:
    scrollbar = ttk.Scrollbar(widget.master)
    widget['yscrollcommand'] = scrollbar.set
    scrollbar['command'] = widget.yview

    # scroll bar must be packed first to make sure that it's always displayed
    scrollbar.pack(side='right', fill='y')
    widget.pack(side='left', fill='both', expand=True)
    return scrollbar


def _calculate_popup_geometry(textwidget: tkinter.Text) -> str:
    bbox = textwidget.bbox('insert')
    assert bbox is not None     # cursor must be visible
    (cursor_x, cursor_y,
     cursor_width, cursor_height) = bbox

    # make coordinates relative to screen
    cursor_x += textwidget.winfo_rootx()
    cursor_y += textwidget.winfo_rooty()

    # leave some space
    cursor_y -= 5
    cursor_height += 10

    popup_width = _SETTINGS['popup_window_width']
    popup_height = _SETTINGS['popup_window_height']
    screen_width = textwidget.winfo_screenwidth()
    screen_height = textwidget.winfo_screenheight()

    # don't go off the screen to the right, leave space between popup
    # and right side of window
    x = min(screen_width - popup_width - 10, cursor_x)

    if cursor_y + cursor_height + popup_height < screen_height:
        # it fits below cursor, put it there
        y = cursor_y + cursor_height
    else:
        # put it above cursor instead. If it doesn't fit there either,
        # then y is also negative and the user has a tiny screen or a
        # huge popup size.
        y = cursor_y - popup_height

    return f'{popup_width}x{popup_height}+{x}+{y}'


class _Popup:

    def __init__(self) -> None:
        self._completion_list: typing.Optional[typing.List[Completion]] = None

        self.toplevel = tkinter.Toplevel()
        self.toplevel.withdraw()
        self.toplevel.overrideredirect(True)

        # from tkinter/ttk.py:
        #
        #   PanedWindow = Panedwindow # tkinter name compatibility
        #
        # I'm using Panedwindow here in case the PanedWindow alias is deleted
        # in a future version of python.
        self._panedwindow = ttk.Panedwindow(
            self.toplevel, orient='horizontal')
        self._panedwindow.pack(fill='both', expand=True)

        left_pane = ttk.Frame(self._panedwindow)
        right_pane = ttk.Frame(self._panedwindow)
        self._panedwindow.add(left_pane)
        self._panedwindow.add(right_pane)

        self.treeview = ttk.Treeview(
            left_pane, show='tree', selectmode='browse')
        self.treeview.bind('<Motion>', self._on_mouse_move)
        self.treeview.bind('<<TreeviewSelect>>', self._on_select)
        self._left_scrollbar = _pack_with_scrollbar(self.treeview)

        self._doc_text = utils.create_passive_text_widget(
            right_pane, width=50, height=15, wrap='word')
        self._right_scrollbar = _pack_with_scrollbar(self._doc_text)

        self._resize_handle = ttk.Sizegrip(self.toplevel)
        self._resize_handle.place(relx=1, rely=1, anchor='se')
        self.toplevel.bind('<Configure>', self._on_anything_resized)

    def _on_anything_resized(self, junk: tkinter.Event) -> None:
        # When the separator is dragged all the way to left or the popup is
        # resized to be narrow enough, the right scrollbar is no longer mapped
        # (i.e. visible) but the left scrollbar must get out of the way of the
        # resize handle. Otherwise the left scrollbar can go all the way to the
        # bottom of the popup, but the right scrollbar must make room.
        handle_height = self._resize_handle.winfo_height()
        if self._right_scrollbar.winfo_ismapped():
            self._left_scrollbar.pack(pady=(0, 0))
            self._right_scrollbar.pack(pady=(0, handle_height))
        else:
            self._left_scrollbar.pack(pady=(0, handle_height))
            self._right_scrollbar.pack(pady=(0, 0))

    # When tab is pressed with popups turned off in settings, this goes to a
    # state where it's completing but not showing.

    def is_completing(self) -> bool:
        return (self._completion_list is not None)

    def is_showing(self) -> bool:
        # don't know how only one of them could be mapped, checking to be sure
        return bool(self.toplevel.winfo_ismapped() and
                    self._panedwindow.winfo_ismapped())

    def _select_item(self, item_id: str) -> None:
        self.treeview.selection_set(item_id)
        self.treeview.see(item_id)

    def _get_selected_completion(self) -> typing.Optional[Completion]:
        if not self.is_completing():
            return None
        assert self._completion_list is not None

        selected_ids = self.treeview.selection()
        if not selected_ids:
            return None

        [the_id] = selected_ids
        return self._completion_list[int(the_id)]

    def start_completing(self, completion_list: typing.List[Completion],
                         geometry: typing.Optional[str] = None) -> None:
        if self.is_completing():
            self.stop_completing(withdraw=False)

        self._completion_list = completion_list

        if completion_list:
            for index, completion in enumerate(completion_list):
                # id=str(index) is used in the rest of this class
                self.treeview.insert('', 'end', id=str(index),
                                     text=completion.display_text)
            self._select_item('0')
        else:
            self._doc_text['state'] = 'normal'
            self._doc_text.delete('1.0', 'end')
            self._doc_text.insert('1.0', "No completions")
            self._doc_text['state'] = 'disabled'

        if geometry is not None:
            self.toplevel.geometry(geometry)
        self.toplevel.deiconify()

        # don't know why after_idle is needed, but it is
        def set_correct_sashpos() -> None:
            self._panedwindow.sashpos(0, _SETTINGS['popup_divider_pos'])

        self._panedwindow.after_idle(set_correct_sashpos)

    # does nothing if not currently completing
    # returns selected completion dict or None if no completions
    def stop_completing(
            self, *, withdraw: bool = True) -> typing.Optional[Completion]:
        # putting this here avoids some bugs
        if self.is_showing():
            _SETTINGS['popup_window_width'] = self.toplevel.winfo_width()
            _SETTINGS['popup_window_height'] = self.toplevel.winfo_height()
            _SETTINGS['popup_divider_pos'] = self._panedwindow.sashpos(0)

        selected = self._get_selected_completion()

        if withdraw:
            self.toplevel.withdraw()
        self.treeview.delete(*self.treeview.get_children())
        self._completion_list = None

        return selected

    def select_previous(self) -> None:
        assert self.is_completing()
        selected_ids = self.treeview.selection()
        if selected_ids:
            [the_id] = selected_ids
            self._select_item(
                self.treeview.prev(the_id) or self.treeview.get_children()[-1])

    def select_next(self) -> None:
        assert self.is_completing()
        selected_ids = self.treeview.selection()
        if selected_ids:
            [the_id] = selected_ids
            self._select_item(
                self.treeview.next(the_id) or self.treeview.get_children()[0])

    def on_page_up_down(self, event: tkinter.Event) -> utils.BreakOrNone:
        if not self.is_showing():
            return None

        page_count = {'Prior': -1, 'Next': 1}[event.keysym]
        self._doc_text.yview_scroll(page_count, 'pages')
        return 'break'

    def on_arrow_key_up_down(self, event: tkinter.Event) -> utils.BreakOrNone:
        if not self.is_showing():
            return None

        method = {'Up': self.select_previous,
                  'Down': self.select_next}[event.keysym]
        method()
        return 'break'

    def _on_mouse_move(self, event: tkinter.Event) -> None:
        hovered_id = self.treeview.identify_row(event.y)
        if hovered_id:
            self.treeview.selection_set(hovered_id)

    def _on_select(self, event: tkinter.Event) -> None:
        completion = self._get_selected_completion()
        if completion is not None:
            self._doc_text['state'] = 'normal'
            self._doc_text.delete('1.0', 'end')
            self._doc_text.insert('1.0', completion.documentation)
            self._doc_text['state'] = 'disabled'


@dataclasses.dataclass
class Request(utils.EventDataclass):
    id: int
    cursor_pos: str


@dataclasses.dataclass
class Response(utils.EventDataclass):
    id: int
    completions: typing.List[Completion]


# How this differs from using sometextwidget.compare(start, '<', end):
#   - This does the right thing if text has been deleted so that start and end
#     no longer exist in the text widget.
#   - Start and end must be in 'x.y' format.
def text_index_less_than(index1: str, index2: str) -> bool:
    tuple1 = tuple(map(int, index1.split('.')))
    tuple2 = tuple(map(int, index2.split('.')))
    return (tuple1 < tuple2)


class AutoCompleter:

    def __init__(self, tab: tabs.FileTab) -> None:
        self._tab = tab
        self._orig_cursorpos: typing.Optional[str] = None
        self._id_counter = itertools.count()
        self._waiting_for_response_id: typing.Optional[int] = None
        self.popup = _Popup()

    def _request_completions(self) -> None:
        the_id = next(self._id_counter)
        self._waiting_for_response_id = the_id

        # use this cursor pos when needed because while processing the
        # completion request or filtering, user might type more
        self._orig_cursorpos = self._tab.textwidget.index('insert')

        self._tab.event_generate('<<AutoCompletionRequest>>', data=Request(
            id=the_id,
            cursor_pos=self._orig_cursorpos,
        ))

    def _user_wants_to_see_popup(self, cursor_pos_when_completing_started: str) -> bool:
        initial_line, initial_column = map(int, cursor_pos_when_completing_started.split('.'))
        current_line, current_column = map(int, self._tab.textwidget.index('insert').split('.'))

        # Make sure that while waiting for completions, the user didn't
        #   - switch porcupine tab
        #   - switch to a different window
        #   - move the cursor to another line
        #   - move the cursor back before where it was initially
        #
        # Moving the cursor forward to filter through the list is allowed as
        # long as the cursor stays on the same line.
        return (self._tab.focus_get() == self._tab.textwidget and
                current_line == initial_line and
                current_column >= initial_column)

    # this might not run for all requests if e.g. langserver not configured
    def receive_completions(self, event: utils.EventWithData) -> None:
        response = event.data_class(Response)
        if response.id != self._waiting_for_response_id:
            return
        self._waiting_for_response_id = None

        if self._user_wants_to_see_popup(info_dict['cursor_pos']):
            self.unfiltered_completions = info_dict['completions']
            self.popup.start_completing(
                self._get_filtered_completions(),
                calculate_popup_geometry(self._tab.textwidget))

    # this doesn't work perfectly. After get<Tab>, getar_u matches
    # getchar_unlocked but getch_u doesn't.
    def _get_filtered_completions(self) -> typing.List[Completion]:
        assert self._orig_cursorpos is not None
        filter_text = self._tab.textwidget.get(self._orig_cursorpos, 'insert')

        return [
            completion for completion in self.unfiltered_completions
            if filter_text.lower() in completion.filter_text.lower()
        ]

    # returns None if this isn't a place where it's good to autocomplete
    def _can_complete_here(self) -> bool:
        before_cursor = self._tab.textwidget.get('insert linestart', 'insert')
        after_cursor = self._tab.textwidget.get('insert', 'insert lineend')

        # don't complete in beginning of line or with space before cursor
        if not re.search(r'\S$', before_cursor):
            return False

        # don't complete in the beginning or middle of a word
        if re.search(r'^\w', after_cursor):
            return False

        return True

    def on_tab(self, event: tkinter.Event, shifted: bool) -> utils.BreakOrNone:
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

    def _accept(self) -> None:
        if not self.popup.is_completing():
            return

        completion = self.popup.stop_completing()
        if completion is not None:
            assert self._orig_cursorpos is not None
            self._tab.textwidget.delete(self._orig_cursorpos, 'insert')
            self._tab.textwidget.replace(
                completion.replace_start, completion.replace_end,
                completion.replace_text)

        self._waiting_for_response_id = None
        self._orig_cursorpos = None

    def _reject(self) -> None:
        if self.popup.is_completing():
            self.popup.stop_completing()
            self._waiting_for_response_id = None
            self._orig_cursorpos = None

    def on_any_key(self, event: tkinter.Event) -> None:
        if event.keysym.startswith('Shift'):
            return

        if self.popup.is_completing():
            # TODO: use language-specific identifier character?
            its_just_a_letter = bool(re.fullmatch(r'\w', event.char))
            if (not its_just_a_letter) and event.keysym != 'BackSpace':
                self._reject()
                return

            # let the text get inserted before continuing
            self._tab.textwidget.after_idle(self._filter_through_completions)

        else:
            if event.char in self._tab.filetype.autocomplete_chars:
                def do_request() -> None:
                    if ((not self.popup.is_completing())
                            and self._can_complete_here()):
                        self._request_completions()

                # Tiny delay added to make sure that langserver's change events
                # get sent before completions are requested.
                self._tab.after(10, do_request)
                self._waiting_for_response_id = None
                return

    # Completing should stop when newline is inserted with or without pressing
    # the enter key. Pasting is one way to insert newline without enter press.
    # Currently this works, but if you modify this code, then make sure that
    # it still works.
    #
    # TODO: is it possible to write a test for this?

    def _filter_through_completions(self) -> None:
        assert self._orig_cursorpos is not None

        # if cursor has moved back more since requesting completions: User
        # has backspaced away a lot and likely doesn't want completions.
        if text_index_less_than(
                self._tab.textwidget.index('insert'), self._orig_cursorpos):
            self._reject()
            return

        self.popup.stop_completing(withdraw=False)
        self.popup.start_completing(self._get_filtered_completions())

    def on_enter(self, event: tkinter.Event) -> utils.BreakOrNone:
        if self.popup.is_completing():
            self._accept()
            return 'break'
        return None

    def on_escape(self, event: tkinter.Event) -> utils.BreakOrNone:
        if self.popup.is_completing():
            self._reject()
            return 'break'
        return None


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if not isinstance(tab, tabs.FileTab):
        return

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

    tab.bind('<Destroy>', (lambda event: completer.popup.toplevel.destroy()),
             add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)

    _SETTINGS.add_label(
        # TODO: link to langserver setup docs here
        "If autocompletion isn't working, make sure that you have langserver "
        "set up correctly.")

    _SETTINGS.add_option('popup_window_width', 500, reset=False)
    _SETTINGS.add_option('popup_window_height', 200, reset=False)
    _SETTINGS.add_option('popup_divider_pos', 200, reset=False)
