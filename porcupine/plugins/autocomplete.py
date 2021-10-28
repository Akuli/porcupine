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
from typing import List

from porcupine import get_tab_manager, settings, tabs, textutils, utils

# autoindent: it shouldn't indent when pressing enter to choose completion
# tabs2spaces: all plugins binding tab or shift+tab must bind first
setup_before = ["autoindent", "tabs2spaces"]

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Completion:
    display_text: str
    replace_start: str
    replace_end: str
    replace_text: str
    filter_text: str
    documentation: str


@dataclasses.dataclass
class Request(utils.EventDataclass):
    id: int
    cursor_pos: str


@dataclasses.dataclass
class Response(utils.EventDataclass):
    id: int
    completions: List[Completion]


def _pack_with_scrollbar(widget: ttk.Treeview | tkinter.Text) -> ttk.Scrollbar:
    scrollbar = ttk.Scrollbar(widget.master)
    widget.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=widget.yview)

    # scroll bar must be packed first to make sure that it's always displayed
    scrollbar.pack(side="right", fill="y")
    widget.pack(side="left", fill="both", expand=True)
    return scrollbar


# can't use ttk.Sizegrip, that is only for resizing tkinter.Toplevel or tkinter.Tk
def _add_resize_handle(placed_widget: tkinter.Widget) -> ttk.Label:
    between_mouse_and_widget_bottom_right_corner = [0, 0]

    # Doing this only in the beginning of resize ensures that if it's off by 1
    # for whatever reason, then it will only ever be off by 1 pixel, rather
    # than off by 1 pixel MORE for each resize event.
    def begin_resize(event: tkinter.Event[ttk.Label]) -> None:
        between_mouse_and_widget_bottom_right_corner[:] = [
            event.widget.winfo_width() - event.x,
            event.widget.winfo_height() - event.y,
        ]

    def do_resize(event: tkinter.Event[ttk.Label]) -> None:
        x_offset, y_offset = between_mouse_and_widget_bottom_right_corner
        width = max(1, event.x_root - placed_widget.winfo_rootx() + x_offset)
        height = max(1, event.y_root - placed_widget.winfo_rooty() + y_offset)
        placed_widget.place(width=width, height=height)

        settings.set_("autocomplete_popup_width", width)
        settings.set_("autocomplete_popup_height", height)

    handle = ttk.Label(placed_widget, text="⇲")  # unicode awesomeness
    handle.bind("<Button-1>", begin_resize, add=True)
    handle.bind("<Button1-Motion>", do_resize, add=True)
    handle.place(relx=1, rely=1, anchor="se")
    return handle


class _Popup:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self._textwidget = textwidget
        self._completion_list: list[Completion] | None = None

        self._panedwindow = utils.PanedWindow(self._textwidget, orient="horizontal")

        normal_cursor = self._textwidget["cursor"]
        self._panedwindow.bind(
            "<Enter>", (lambda event: textwidget.config(cursor="arrow")), add=True
        )
        self._panedwindow.bind(
            "<Leave>", (lambda event: textwidget.config(cursor=normal_cursor)), add=True
        )

        left_pane = ttk.Frame(self._panedwindow)
        right_pane = ttk.Frame(self._panedwindow)
        self._panedwindow.add(left_pane)
        self._panedwindow.add(right_pane)
        settings.remember_pane_size(self._panedwindow, left_pane, "autocomplete_popup_divider", 200)

        self.treeview = ttk.Treeview(left_pane, show="tree", selectmode="browse")
        self.treeview.bind("<Motion>", self._on_mouse_move, add=True)
        self.treeview.bind("<<TreeviewSelect>>", self._on_select, add=True)
        self._left_scrollbar = _pack_with_scrollbar(self.treeview)

        self._doc_text = textutils.create_passive_text_widget(
            right_pane, width=50, height=15, wrap="word"
        )
        self._right_scrollbar = _pack_with_scrollbar(self._doc_text)

        self._resize_handle = _add_resize_handle(self._panedwindow)
        self._panedwindow.bind("<Configure>", self._on_resize, add=True)

    def _on_resize(self, junk: object = None) -> None:
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

    def _select_item(self, item_id: str) -> None:
        self.treeview.selection_set(item_id)
        self.treeview.see(item_id)

    def _get_selected_completion(self) -> Completion | None:
        if not self.is_completing():
            return None
        assert self._completion_list is not None

        selected_ids = self.treeview.selection()
        if not selected_ids:
            return None

        [the_id] = selected_ids
        return self._completion_list[int(the_id)]

    def set_completions(self, completion_list: list[Completion]) -> None:
        self.treeview.delete(*self.treeview.get_children())

        self._completion_list = completion_list
        if self._completion_list:
            for index, completion in enumerate(self._completion_list):
                # id=str(index) is used in the rest of this class
                self.treeview.insert("", "end", id=str(index), text=completion.display_text)
            self._select_item("0")
        else:
            self._doc_text.config(state="normal")
            self._doc_text.delete("1.0", "end")
            self._doc_text.insert("1.0", "No completions")
            self._doc_text.config(state="disabled")

    def start_completing(self) -> None:
        if textutils.place_popup(
            self._textwidget,
            self._panedwindow,
            width=settings.get("autocomplete_popup_width", int),
            height=settings.get("autocomplete_popup_height", int),
        ):
            self._panedwindow.update()  # _on_resize() uses current sizes
            self._on_resize()

    # does nothing if not currently completing
    def stop_completing(self) -> Completion | None:
        selected = self._get_selected_completion()
        self._panedwindow.place_forget()
        self._completion_list = None
        return selected

    def select_previous(self) -> None:
        assert self.is_completing()
        selected_ids = self.treeview.selection()
        if selected_ids:
            [the_id] = selected_ids
            self._select_item(self.treeview.prev(the_id) or self.treeview.get_children()[-1])

    def select_next(self) -> None:
        assert self.is_completing()
        selected_ids = self.treeview.selection()
        if selected_ids:
            [the_id] = selected_ids
            self._select_item(self.treeview.next(the_id) or self.treeview.get_children()[0])

    def _get_first_visible_id(self) -> int:
        # First id is "0", second is "1" etc
        for item_id in self.treeview.get_children():
            if self.treeview.bbox(item_id):
                return int(item_id)
        raise RuntimeError("wut")

    def on_page_up_down(self, event: tkinter.Event[tkinter.Misc]) -> str | None:
        if not self._panedwindow.winfo_ismapped():
            return None

        page_count = {"Prior": -1, "Next": 1}[event.keysym]
        old_selection = self.treeview.selection()

        old_first_visible = self._get_first_visible_id()
        self.treeview.yview_scroll(page_count, "pages")
        self.treeview.update()
        new_first_visible = self._get_first_visible_id()

        # Move selection as scrolled
        if old_selection:
            [old_id] = old_selection
            rows_scrolled = new_first_visible - old_first_visible
            new_id = str(int(old_id) + rows_scrolled)
            self.treeview.selection_set(new_id)

        return "break"

    def on_arrow_key_up_down(self, event: tkinter.Event[tkinter.Misc]) -> str | None:
        if not self._panedwindow.winfo_ismapped():
            return None

        method = {"Up": self.select_previous, "Down": self.select_next}[event.keysym]
        method()
        return "break"

    def _on_mouse_move(self, event: tkinter.Event[tkinter.Misc]) -> None:
        hovered_id = self.treeview.identify_row(event.y)
        if hovered_id:
            self.treeview.selection_set(hovered_id)

    def _on_select(self, event: tkinter.Event[tkinter.Misc]) -> None:
        completion = self._get_selected_completion()
        if completion is not None:
            self._doc_text.config(state="normal")
            self._doc_text.delete("1.0", "end")
            self._doc_text.insert("1.0", completion.documentation)
            self._doc_text.config(state="disabled")


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

    completions = [
        Completion(
            display_text=word,
            replace_start=word_start,
            replace_end=request.cursor_pos,
            replace_text=word,
            filter_text=word,
            documentation=word,
        )
        for word in words
    ]
    tab.event_generate(
        "<<AutoCompletionResponse>>",
        data=Response(
            id=request.id, completions=completions[:200]  # don't be ridulously slow in huge files
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
        self._orig_cursorpos: str | None = None
        self._id_counter = itertools.count()
        self._waiting_for_response_id: int | None = None
        self.popup = _Popup(tab.textwidget)
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
            self.popup.set_completions(self._get_filtered_completions())
            self.popup.start_completing()

    # this doesn't work perfectly. After get<Tab>, getar_u matches
    # getchar_unlocked but getch_u doesn't.
    def _get_filtered_completions(self) -> list[Completion]:
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
            assert self._orig_cursorpos is not None
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
        else:
            self.popup.set_completions(self._get_filtered_completions())

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

    # Don't know why <Button> does not include <Button-1> in this context
    tab.textwidget.bind("<Button>", (lambda event: completer._reject()), add=True)
    tab.textwidget.bind("<Button-1>", (lambda event: completer._reject()), add=True)

    # fallback completer, other completers must be bound before
    utils.bind_with_data(
        tab, "<<AutoCompletionRequest>>", partial(_all_words_in_file_completer, tab), add=True
    )


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    settings.add_option("autocomplete_popup_width", 500)
    settings.add_option("autocomplete_popup_height", 200)
