"""Autocompletions.

To get the most out of this plugin, you also need some other plugin such as the
langserver plugin. If no such plugin is loaded, then this plugin falls back to
"all words in file" style autocompletions.
"""

# If your plugin sets up an autocompleter, it should be setup before this
# plugin. That way its <<AutoCompletionRequest>> binding will be used instead
# of the all-words-in-file fallback.

from __future__ import annotations

import collections
import dataclasses
import itertools
import logging
import re
import tkinter
from functools import partial
from tkinter import ttk
from typing import List, Optional, Union

from porcupine import get_main_window, get_tab_manager, settings, tabs, textutils, utils

setup_before = ["tabs2spaces"]  # see tabs2spaces.py

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Completion:
    display_text: str
    replace_start: str
    replace_end: str
    replace_text: str
    filter_text: str
    documentation: str


def _pack_with_scrollbar(widget: Union[ttk.Treeview, tkinter.Text]) -> ttk.Scrollbar:
    scrollbar = ttk.Scrollbar(widget.master)
    widget.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=widget.yview)

    # scroll bar must be packed first to make sure that it's always displayed
    scrollbar.pack(side="right", fill="y")
    widget.pack(side="left", fill="both", expand=True)
    return scrollbar


def _calculate_popup_geometry(textwidget: tkinter.Text) -> str:
    bbox = textwidget.bbox("insert")
    assert bbox is not None  # cursor must be visible
    (cursor_x, cursor_y, cursor_width, cursor_height) = bbox

    # make coordinates relative to screen
    cursor_x += textwidget.winfo_rootx()
    cursor_y += textwidget.winfo_rooty()

    # leave some space
    cursor_y -= 5
    cursor_height += 10

    popup_width = settings.get("autocomplete_popup_width", int)
    popup_height = settings.get("autocomplete_popup_height", int)
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

    return f"{popup_width}x{popup_height}+{x}+{y}"


class _Popup:
    def __init__(self) -> None:
        self._completion_list: Optional[List[Completion]] = None

        self.toplevel = tkinter.Toplevel()
        self.toplevel.withdraw()
        self.toplevel.overrideredirect(True)

        # from tkinter/ttk.py:
        #
        #   PanedWindow = Panedwindow # tkinter name compatibility
        #
        # I'm using Panedwindow here in case the PanedWindow alias is deleted
        # in a future version of python.
        self._panedwindow = ttk.Panedwindow(self.toplevel, orient="horizontal")
        settings.remember_divider_positions(self._panedwindow, "autocomplete_dividers", [200])
        self._panedwindow.pack(fill="both", expand=True)

        left_pane = ttk.Frame(self._panedwindow)
        right_pane = ttk.Frame(self._panedwindow)
        self._panedwindow.add(left_pane)  # type: ignore[no-untyped-call]
        self._panedwindow.add(right_pane)  # type: ignore[no-untyped-call]

        self.treeview = ttk.Treeview(left_pane, show="tree", selectmode="browse")
        self.treeview.bind("<Motion>", self._on_mouse_move, add=True)
        self.treeview.bind("<<TreeviewSelect>>", self._on_select, add=True)
        self._left_scrollbar = _pack_with_scrollbar(self.treeview)

        self._doc_text = textutils.create_passive_text_widget(
            right_pane, width=50, height=15, wrap="word"
        )
        self._right_scrollbar = _pack_with_scrollbar(self._doc_text)

        self._resize_handle = ttk.Sizegrip(self.toplevel)
        self._resize_handle.place(relx=1, rely=1, anchor="se")
        self.toplevel.bind("<Configure>", self._on_anything_resized, add=True)

    def _on_anything_resized(self, junk: object) -> None:
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
        return self._completion_list is not None

    def is_showing(self) -> bool:
        # don't know how only one of them could be mapped, checking to be sure
        return bool(self.toplevel.winfo_ismapped() and self._panedwindow.winfo_ismapped())

    def _select_item(self, item_id: str) -> None:
        self.treeview.selection_set(item_id)  # type: ignore[no-untyped-call]
        self.treeview.see(item_id)  # type: ignore[no-untyped-call]

    def _get_selected_completion(self) -> Optional[Completion]:
        if not self.is_completing():
            return None
        assert self._completion_list is not None

        selected_ids = self.treeview.selection()
        if not selected_ids:
            return None

        [the_id] = selected_ids
        return self._completion_list[int(the_id)]

    def start_completing(
        self, completion_list: List[Completion], geometry: Optional[str] = None
    ) -> None:
        if self.is_completing():
            self.stop_completing(withdraw=False)

        self._completion_list = completion_list

        if completion_list:
            for index, completion in enumerate(completion_list):
                # id=str(index) is used in the rest of this class
                self.treeview.insert("", "end", id=str(index), text=completion.display_text)
            self._select_item("0")
        else:
            self._doc_text.config(state="normal")
            self._doc_text.delete("1.0", "end")
            self._doc_text.insert("1.0", "No completions")
            self._doc_text.config(state="disabled")

        if geometry is not None:
            self.toplevel.geometry(geometry)
        self.toplevel.deiconify()

    # does nothing if not currently completing
    # returns selected completion dict or None if no completions
    def stop_completing(self, *, withdraw: bool = True) -> Optional[Completion]:
        # putting this here avoids some bugs
        if self.is_showing():
            settings.set_("autocomplete_popup_width", self.toplevel.winfo_width())
            settings.set_("autocomplete_popup_height", self.toplevel.winfo_height())

        selected = self._get_selected_completion()

        if withdraw:
            self.toplevel.withdraw()
        self.treeview.delete(*self.treeview.get_children())  # type: ignore[no-untyped-call]
        self._completion_list = None

        return selected

    def select_previous(self) -> None:
        assert self.is_completing()
        selected_ids = self.treeview.selection()
        if selected_ids:
            [the_id] = selected_ids
            self._select_item(self.treeview.prev(the_id) or self.treeview.get_children()[-1])  # type: ignore[no-untyped-call]

    def select_next(self) -> None:
        assert self.is_completing()
        selected_ids = self.treeview.selection()
        if selected_ids:
            [the_id] = selected_ids
            self._select_item(self.treeview.next(the_id) or self.treeview.get_children()[0])  # type: ignore[no-untyped-call]

    def on_page_up_down(self, event: tkinter.Event[tkinter.Misc]) -> str | None:
        if not self.is_showing():
            return None

        page_count = {"Prior": -1, "Next": 1}[event.keysym]
        self._doc_text.yview_scroll(page_count, "pages")  # type: ignore[no-untyped-call]
        return "break"

    def on_arrow_key_up_down(self, event: tkinter.Event[tkinter.Misc]) -> str | None:
        if not self.is_showing():
            return None

        method = {"Up": self.select_previous, "Down": self.select_next}[event.keysym]
        method()
        return "break"

    def _on_mouse_move(self, event: tkinter.Event[tkinter.Misc]) -> None:
        hovered_id = self.treeview.identify_row(event.y)  # type: ignore[no-untyped-call]
        if hovered_id:
            self.treeview.selection_set(hovered_id)  # type: ignore[no-untyped-call]

    def _on_select(self, event: tkinter.Event[tkinter.Misc]) -> None:
        completion = self._get_selected_completion()
        if completion is not None:
            self._doc_text.config(state="normal")
            self._doc_text.delete("1.0", "end")
            self._doc_text.insert("1.0", completion.documentation)
            self._doc_text.config(state="disabled")


@dataclasses.dataclass
class Request(utils.EventDataclass):
    id: int
    cursor_pos: str


@dataclasses.dataclass
class Response(utils.EventDataclass):
    id: int
    completions: List[Completion]


# stupid fallback
def _all_words_in_file_completer(tab: tabs.FileTab, event: utils.EventWithData) -> str:
    request = event.data_class(Request)
    match = re.search(
        r"\w*$", tab.textwidget.get(f"{request.cursor_pos} linestart", request.cursor_pos)
    )
    assert match is not None
    before_cursor = match.group(0)
    word_start = tab.textwidget.index(f"{request.cursor_pos} - {len(before_cursor)} chars")

    counts = dict(
        collections.Counter(
            [
                word
                for word in re.findall(
                    r"\w+",
                    (
                        tab.textwidget.get("1.0", word_start)
                        + " "
                        + tab.textwidget.get(request.cursor_pos, "end")
                    ),
                )
                if before_cursor.casefold() in word.casefold()
            ]
        )
    )

    words = list(counts.keys())
    words.sort(
        key=lambda word: (
            # Prefer prefixes
            1 if word.startswith(before_cursor) else 2,
            # Prefer case-sensitive matches (insensitive included too)
            1 if before_cursor in word else 2,
            # Most common goes first
            -counts[word],
            # Short first
            len(word),
            # Alphabetically just to get consistent results
            word,
        )
    )

    tab.event_generate(
        "<<AutoCompletionResponse>>",
        data=Response(
            id=request.id,
            completions=[
                Completion(
                    display_text=word,
                    replace_start=word_start,
                    replace_end=request.cursor_pos,
                    replace_text=word,
                    filter_text=word,
                    documentation=word,
                )
                for word in words
            ],
        ),
    )
    return "break"


# How this differs from using sometextwidget.compare(start, '<', end):
#   - This does the right thing if text has been deleted so that start and end
#     no longer exist in the text widget.
#   - Start and end must be in 'x.y' format.
def _text_index_less_than(index1: str, index2: str) -> bool:
    tuple1 = tuple(map(int, index1.split(".")))
    tuple2 = tuple(map(int, index2.split(".")))
    return tuple1 < tuple2


class AutoCompleter:
    def __init__(self, tab: tabs.FileTab) -> None:
        self._tab = tab
        self._orig_cursorpos: Optional[str] = None
        self._id_counter = itertools.count()
        self._waiting_for_response_id: Optional[int] = None
        self.popup = _Popup()
        utils.bind_with_data(
            tab,
            "<<AutoCompletionResponse>>",
            lambda event: self.receive_completions(event.data_class(Response)),
            add=True,
        )

    def _request_completions(self) -> None:
        log.debug("requesting completions")
        the_id = next(self._id_counter)
        self._waiting_for_response_id = the_id

        # use this cursor pos when needed because while processing the
        # completion request or filtering, user might type more
        self._orig_cursorpos = self._tab.textwidget.index("insert")

        self._tab.event_generate(
            "<<AutoCompletionRequest>>", data=Request(id=the_id, cursor_pos=self._orig_cursorpos)
        )

    def _user_wants_to_see_popup(self) -> bool:
        assert self._orig_cursorpos is not None
        initial_line, initial_column = map(int, self._orig_cursorpos.split("."))
        current_line, current_column = map(int, self._tab.textwidget.index("insert").split("."))

        # Make sure that while waiting for completions, the user didn't
        #   - switch porcupine tab
        #   - switch to a different window
        #   - move the cursor to another line
        #   - move the cursor back before where it was initially
        #
        # Moving the cursor forward to filter through the list is allowed as
        # long as the cursor stays on the same line.
        return (
            self._tab.focus_get() == self._tab.textwidget
            and current_line == initial_line
            and current_column >= initial_column
        )

    # this might not run for all requests if e.g. langserver not configured
    def receive_completions(self, response: Response) -> None:
        log.debug(f"receiving completions: {response}")

        if response.id != self._waiting_for_response_id:
            return
        self._waiting_for_response_id = None

        if self._user_wants_to_see_popup():
            self.unfiltered_completions = response.completions
            self.popup.start_completing(
                self._get_filtered_completions(), _calculate_popup_geometry(self._tab.textwidget)
            )

    # this doesn't work perfectly. After get<Tab>, getar_u matches
    # getchar_unlocked but getch_u doesn't.
    def _get_filtered_completions(self) -> List[Completion]:
        log.debug("getting filtered completions")
        assert self._orig_cursorpos is not None
        filter_text = self._tab.textwidget.get(self._orig_cursorpos, "insert")

        return [
            completion
            for completion in self.unfiltered_completions
            if filter_text.lower() in completion.filter_text.lower()
        ]

    # returns None if this isn't a place where it's good to autocomplete
    def _can_complete_here(self) -> bool:
        before_cursor = self._tab.textwidget.get("insert linestart", "insert")
        after_cursor = self._tab.textwidget.get("insert", "insert lineend")

        # don't complete in beginning of line or with space before cursor
        if not re.search(r"\S$", before_cursor):
            return False

        # don't complete in the beginning or middle of a word
        if re.search(r"^\w", after_cursor):
            return False

        return True

    def on_tab(self, event: tkinter.Event[tkinter.Misc], shifted: bool) -> str | None:
        if self._tab.textwidget.tag_ranges("sel"):
            # something's selected, autocompleting is not the right thing to do
            return None

        if not self.popup.is_completing():
            if not self._can_complete_here():
                # let tabs2spaces and other plugins handle it
                return None

            self._request_completions()
            return "break"

        if shifted:
            self.popup.select_previous()
        else:
            self.popup.select_next()
        return "break"

    def _accept(self) -> None:
        if not self.popup.is_completing():
            return

        log.debug("accepting")
        completion = self.popup.stop_completing()
        if completion is not None:
            assert self._orig_cursorpos is not None
            self._tab.textwidget.delete(self._orig_cursorpos, "insert")
            self._tab.textwidget.replace(
                completion.replace_start, completion.replace_end, completion.replace_text
            )

        self._waiting_for_response_id = None
        self._orig_cursorpos = None

    def _reject(self) -> None:
        if self.popup.is_completing():
            log.debug("rejecting")
            self.popup.stop_completing()
            self._waiting_for_response_id = None
            self._orig_cursorpos = None

    def on_any_key(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if event.keysym.startswith("Shift"):
            return

        if self.popup.is_completing():
            # TODO: use language-specific identifier character?
            its_just_a_letter = bool(re.fullmatch(r"\w", event.char))
            if (not its_just_a_letter) and event.keysym != "BackSpace":
                self._reject()
                return

            # let the text get inserted before continuing
            self._tab.textwidget.after_idle(self._filter_through_completions)

        elif event.char in self._tab.settings.get("autocomplete_chars", List[str]):

            def do_request() -> None:
                if (not self.popup.is_completing()) and self._can_complete_here():
                    self._request_completions()

            # Tiny delay added to make sure that langserver's change events
            # get sent before completions are requested.
            self._tab.after(10, do_request)
            self._waiting_for_response_id = None

    # Completing should stop when newline is inserted with or without pressing
    # the enter key. Pasting is one way to insert newline without enter press.
    # Currently this works, but if you modify this code, then make sure that
    # it still works.
    #
    # TODO: is it possible to write a test for this?

    def _filter_through_completions(self) -> None:
        log.debug("filtering through completions")
        assert self._orig_cursorpos is not None

        # if cursor has moved back more since requesting completions: User
        # has backspaced away a lot and likely doesn't want completions.
        if _text_index_less_than(self._tab.textwidget.index("insert"), self._orig_cursorpos):
            self._reject()
            return

        self.popup.stop_completing(withdraw=False)  # TODO: is this needed?
        self.popup.start_completing(self._get_filtered_completions())

    def on_enter(self, event: tkinter.Event[tkinter.Misc]) -> str | None:
        if self.popup.is_completing():
            self._accept()
            return "break"
        return None

    def on_escape(self, event: tkinter.Event[tkinter.Misc]) -> str | None:
        if self.popup.is_completing():
            self._reject()
            return "break"
        return None


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("autocomplete_chars", [], List[str])

    completer = AutoCompleter(tab)

    # no idea why backspace has to be bound separately
    utils.bind_with_data(tab.textwidget, "<Key>", completer.on_any_key, add=True)
    tab.textwidget.bind("<BackSpace>", completer.on_any_key, add=True)

    utils.bind_tab_key(tab.textwidget, completer.on_tab, add=True)
    tab.textwidget.bind("<Return>", completer.on_enter, add=True)
    tab.textwidget.bind("<Escape>", completer.on_escape, add=True)
    tab.textwidget.bind("<Prior>", completer.popup.on_page_up_down, add=True)
    tab.textwidget.bind("<Next>", completer.popup.on_page_up_down, add=True)
    tab.textwidget.bind("<Up>", completer.popup.on_arrow_key_up_down, add=True)
    tab.textwidget.bind("<Down>", completer.popup.on_arrow_key_up_down, add=True)
    completer.popup.treeview.bind("<Button-1>", (lambda event: completer._accept()), add=True)

    # avoid weird corner cases
    def on_focus_out(event: tkinter.Event[tkinter.Misc]) -> None:
        if event.widget == get_main_window():
            # On Windows, <FocusOut> runs before treeview click handler
            # We must accept when clicked, so reject later
            tab.after_idle(completer._reject)

    get_main_window().bind("<FocusOut>", on_focus_out, add=True)

    # any mouse button
    tab.textwidget.bind("<Button>", (lambda event: completer._reject()), add=True)

    tab.bind("<Destroy>", (lambda event: completer.popup.toplevel.destroy()), add=True)

    # fallback completer, other completers must be bound before
    utils.bind_with_data(
        tab, "<<AutoCompletionRequest>>", partial(_all_words_in_file_completer, tab), add=True
    )


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    settings.add_option("autocomplete_popup_width", 500)
    settings.add_option("autocomplete_popup_height", 200)
