"""Show underlines in code to indicate different things.

Currently the langserver plugin displays errors and warnings with this plugin
and the urls plugin uses this to create control-clickable links.
"""
from __future__ import annotations

import dataclasses
import logging
import tkinter
from typing import Dict, List, Optional

from porcupine import get_main_window, get_tab_manager, tabs, utils

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Underline:
    start: str
    end: str
    message: str
    color: Optional[str] = None


@dataclasses.dataclass
class Underlines(utils.EventDataclass):
    # <<SetUnderlines>> clears previous underlinings with the same id
    id: str
    underline_list: List[Underline]


def _tag_spans_multiple_lines(textwidget: tkinter.Text, tag: str) -> bool:
    first_lineno: str = textwidget.index(f"{tag}.first")[0]
    last_lineno: str = textwidget.index(f"{tag}.last")[0]
    return first_lineno != last_lineno


class _Underliner:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        self.textwidget.bind("<<CursorMoved>>", self._on_cursor_moved, add=True)
        self.textwidget.bind("<<UnderlinerHidePopup>>", self._hide_message_label, add=True)
        self.textwidget.tag_bind("underline_common", "<Enter>", self._on_mouse_enter)
        self.textwidget.tag_bind("underline_common", "<Leave>", self._hide_message_label)
        utils.add_scroll_command(textwidget, "yscrollcommand", self._hide_message_label)

        self._message_label: Optional[tkinter.Label] = None
        self._message_tag: Optional[str] = None
        self._tag2underline: Dict[str, Underline] = {}

    def _show_tag_at_index(self, index: str) -> None:
        # Reversing to prefer topmost tags (i.e. tags added last)
        for tag in reversed(self.textwidget.tag_names(index)):
            if tag in self._tag2underline:
                self._show_message_label(tag)
                return
        self._hide_message_label()

    def _on_mouse_enter(self, junk: object) -> None:
        self._show_tag_at_index("current")

    def _on_cursor_moved(self, junk: object) -> None:
        self._show_tag_at_index("insert")

    def set_underlines(self, event: utils.EventWithData) -> None:
        underlines = event.data_class(Underlines)
        log.debug(f"Setting underlines: {underlines}")
        self.textwidget.tag_remove(f"underline:{underlines.id}", "1.0", "end")

        old_underlines_deleted = False
        for tag in list(self._tag2underline.keys()):
            literally_underline, tag_id, number = tag.split(":")
            if tag_id == underlines.id:
                self.textwidget.tag_delete(tag)
                del self._tag2underline[tag]
                old_underlines_deleted = True

        for index, underline in enumerate(underlines.underline_list):
            tag = f"underline:{underlines.id}:{index}"
            less_specific_tag = f"underline:{underlines.id}"

            self._tag2underline[tag] = underline
            if underline.color is None:
                self.textwidget.tag_config(tag, underline=True)
            else:
                self.textwidget.tag_config(tag, underline=True, underlinefg=underline.color)

            self.textwidget.tag_add(tag, underline.start, underline.end)
            self.textwidget.tag_add(less_specific_tag, underline.start, underline.end)

        # Updating underline_common tag is kind of brute-force because overlapping non-common
        # underline tags make it difficult. But let's not run it at every key press unless something
        # actually changed.
        if old_underlines_deleted or underlines.underline_list:
            self.textwidget.tag_remove("underline_common", "1.0", "end")
            for tag in self._tag2underline.keys():
                ranges = self.textwidget.tag_ranges(tag)
                for start, end in zip(ranges[0::2], ranges[1::2]):
                    self.textwidget.tag_add("underline_common", start, end)

        # update what's showing
        if any(tag.startswith("underline:") for tag in self.textwidget.tag_names("insert")):
            self._show_tag_at_index("insert")
        else:
            self._hide_message_label()

    def _show_message_label(self, tag: str) -> None:
        if self._message_tag == tag:
            return

        self._hide_message_label()

        if _tag_spans_multiple_lines(self.textwidget, tag):
            bbox = self.textwidget.bbox(f"{tag}.last linestart")
        else:
            bbox = self.textwidget.bbox(f"{tag}.first")

        if bbox is None:
            # this is called even though the relevant part of text isn't visible? weird
            return

        bbox_x, bbox_y, bbox_width, bbox_height = bbox
        gap_size = 8

        self._message_tag = tag
        self._message_label = tkinter.Label(
            self.textwidget,
            text=self._tag2underline[tag].message,
            wraplength=(self.textwidget.winfo_width() - 2 * gap_size),
            # opposite colors as in the text widget
            bg=self.textwidget["fg"],
            fg=self.textwidget["bg"],
        )

        label_width = self._message_label.winfo_reqwidth()
        label_height = self._message_label.winfo_reqheight()

        # don't go beyond the right edge of textwidget
        label_x = min(bbox_x, self.textwidget.winfo_width() - gap_size - label_width)

        if bbox_y + bbox_height + gap_size + label_height < self.textwidget.winfo_height():
            # label goes below bbox
            label_y = bbox_y + bbox_height + gap_size
        else:
            # would go below bottom of text widget, let's put it above instead
            label_y = bbox_y - gap_size - label_height
        self._message_label.place(x=label_x, y=label_y)

    def _hide_message_label(self, junk: object = None) -> None:
        if self._message_label is not None:
            self._message_label.destroy()
            self._message_label = None
            self._message_tag = None


def on_new_filetab(tab: tabs.FileTab) -> None:
    underliner = _Underliner(tab.textwidget)
    utils.bind_with_data(tab, "<<SetUnderlines>>", underliner.set_underlines, add=True)


def hide_all_message_labels(event: tkinter.Event[tkinter.Misc]) -> None:
    if event.widget is get_main_window():  # Tk and Toplevel events need this check
        for tab in get_tab_manager().tabs():
            if isinstance(tab, tabs.FileTab):
                tab.textwidget.event_generate("<<UnderlinerHidePopup>>")


def setup() -> None:
    # trigger <<UnderlinerHidePopup>> when text widget goes invisible (e.g. switching tabs)
    get_main_window().event_add("<<UnderlinerHidePopup>>", "<Unmap>")

    # and when the entire porcupine window loses input focus (binding here to avoid unbinding)
    get_main_window().bind("<FocusOut>", hide_all_message_labels, add=True)

    get_tab_manager().add_filetab_callback(on_new_filetab)
