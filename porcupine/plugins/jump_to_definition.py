"""Easily jump to where a function or class was defined.

For this plugin to work, you also need the langserver plugin.
"""
from __future__ import annotations

import dataclasses
import logging
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


def receive_jump(event: utils.EventWithData) -> str | None:
    tab = event.widget
    assert isinstance(tab, tabs.FileTab), repr(tab)
    response = event.data_class(Response)

    # FIXME: there can be multiple ranges
    if not response.location_ranges:
        log.warning("no possible definitions found")
        return None
    range = response.location_ranges[0]

    log.info(f"showing definition to user: {range}")
    path = Path(range.file_path)
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
    tab.textwidget.tag_add("sel", range.start, range.end)
    tab.textwidget.mark_set("insert", range.start)
    tab.textwidget.see("insert")
    return "break"


def on_new_filetab(tab: tabs.FileTab) -> None:
    utils.bind_with_data(tab, "<<JumpToDefinitionResponse>>", receive_jump, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
