"""Show underlines in code to indicate different things.

Currently the langserver plugin displays errors and warnings with this plugin
and the urls plugin uses this to create control-clickable links.
"""
from __future__ import annotations

import dataclasses
import logging
import tkinter
from typing import List, Optional

from porcupine import get_tab_manager, tabs, utils
from porcupine.plugins import hover

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


class _Underliner:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        self._tag2underline: dict[str, Underline] = {}

    def set_underlines(self, event: utils.EventWithData) -> None:
        underlines = event.data_class(Underlines)
        log.debug(f"Setting underlines: {underlines}")
        self.textwidget.tag_remove(f"underline:{underlines.id}", "1.0", "end")

        for tag in list(self._tag2underline.keys()):
            literally_underline, tag_id, number = tag.split(":")
            if tag_id == underlines.id:
                self.textwidget.tag_delete(tag)
                del self._tag2underline[tag]

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

    def handle_hover_request(self, event: utils.EventWithData) -> str | None:
        # Reversing to prefer topmost tags (i.e. tags added last)
        for tag in reversed(self.textwidget.tag_names(event.data_string)):
            if tag in self._tag2underline:
                self.textwidget.event_generate(
                    "<<HoverResponse>>",
                    data=hover.Response(
                        location=event.data_string, text=self._tag2underline[tag].message
                    ),
                )
                return "break"  # Do not pass hover event to langserver
        return None


def on_new_filetab(tab: tabs.FileTab) -> None:
    underliner = _Underliner(tab.textwidget)
    utils.bind_with_data(tab, "<<SetUnderlines>>", underliner.set_underlines, add=True)
    utils.bind_with_data(
        tab.textwidget, "<<HoverRequest>>", underliner.handle_hover_request, add=True
    )


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
