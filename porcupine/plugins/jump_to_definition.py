"""Jump to where a function or class was defined on Ctrl+click or Ctrl+Enter.

For this plugin to work, you also need the langserver plugin.
"""
from __future__ import annotations

import dataclasses
import logging
import tkinter
from functools import partial
from pathlib import Path
from typing import List

from porcupine import get_tab_manager, tabs, utils

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Request(utils.EventDataclass):
    file_path: str  # not pathlib.Path because json
    location: str


@dataclasses.dataclass
class LocationRange:
    file_path: str  # not pathlib.Path because json
    start: str
    end: str


@dataclasses.dataclass
class Response(utils.EventDataclass):
    location_ranges: List[LocationRange]


def show_location_range(loc_range: LocationRange) -> None:
    log.info(f"showing definition to user: {loc_range}")
    path = Path(loc_range.file_path)
    matching_tabs = [
        tab
        for tab in get_tab_manager().tabs()
        if isinstance(tab, tabs.FileTab) and tab.path == path
    ]
    if matching_tabs:
        [tab] = matching_tabs
        get_tab_manager().select(tab)
    else:
        log.info(f"{path} not opened yet, opening now")
        tab = tabs.FileTab.open_file(get_tab_manager(), path)
        get_tab_manager().add_tab(tab, select=True)

    tab.textwidget.tag_remove("sel", "1.0", "end")
    tab.textwidget.tag_add("sel", loc_range.start, loc_range.end)
    tab.textwidget.mark_set("insert", loc_range.start)
    tab.textwidget.see("insert")


def find_cursor_xy(textwidget: tkinter.Text) -> tuple[int, int]:
    bbox = textwidget.bbox("insert")
    assert bbox is not None
    left, top, width, height = bbox

    # Make coords relative to top left corner of screen, not text widget
    left += textwidget.winfo_rootx()
    top += textwidget.winfo_rooty()

    return (left, top + height)


def receive_jump(event: utils.EventWithData) -> str | None:
    tab = event.widget
    assert isinstance(tab, tabs.FileTab), repr(tab)
    response = event.data_class(Response)

    if not response.location_ranges:
        log.warning("no possible definitions found")
    elif len(response.location_ranges) == 1:
        show_location_range(response.location_ranges[0])
    else:
        menu = tkinter.Menu(tearoff=False)

        # Consistent order, first location is first within same file
        sorted_ranges = sorted(
            response.location_ranges,
            key=(
                lambda r: (
                    Path(r.file_path),  # Case insensitive comparing on windows
                    int(r.start.split(".")[0]),  # Line number
                    int(r.start.split(".")[1]),  # Column number in case multiple on same line
                )
            ),
        )

        for loc_range in sorted_ranges:
            menu.add_command(
                # TODO: better menu item text?
                label=f"Line {loc_range.start.split('.')[0]} in {loc_range.file_path}",
                command=partial(show_location_range, loc_range),
            )
        menu.tk_popup(*find_cursor_xy(tab.textwidget))
        menu.bind("<Unmap>", (lambda event: menu.after_idle(menu.destroy)), add=True)


def on_new_filetab(tab: tabs.FileTab) -> None:
    utils.bind_with_data(tab, "<<JumpToDefinitionResponse>>", receive_jump, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
