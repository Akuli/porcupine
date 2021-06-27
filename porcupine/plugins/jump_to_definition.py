"""Easily jump to where a function or class was defined.

For this plugin to work, you also need the langserver plugin.
"""
from __future__ import annotations

import collections
import dataclasses
import itertools
import logging
import re
import tkinter
from tkinter import ttk
from pathlib import Path
from typing import List
from porcupine import get_tab_manager, settings, tabs, textutils, utils,get_main_window

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


class Jumper:
    def request_jump(self, tab: tabs.FileTab) -> None:
        cursor_pos = tab.textwidget.index('insert')
        log.debug(f"user wants to jump to definition of {cursor_pos} in {tab.path}")
        tab.event_generate(
            "<<JumpToDefinitionRequest>>",
            data=cursor_pos,
        )

    # this might not run for all requests if e.g. langserver not configured
    def receive_jump(self, event: utils.EventWithData) -> str | None:
        tab = event.widget
        assert isinstance(tab, tabs.FileTab), repr(tab)
        response = event.data_class(Response)

        # FIXME: there can be multiple ranges
        if not response.location_ranges:
            log.warning("definition not found")
            return None
        range = response.location_ranges[0]

        log.info(f"showing definition to user: {range}")
        path = Path(range.file_path)
        matching_tabs = [tab for tab in get_tab_manager().tabs() if isinstance(tab, tabs.FileTab) and tab.path == path]
        if matching_tabs:
            [tab]=matching_tabs
            get_tab_manager().select(tab)
        else:
            log.info(f"{path} not opened yet, opening now")
            # Need to make new tab
            tab = tabs.FileTab.open_file(get_tab_manager(), path)
            get_tab_manager().add_tab(tab, select=True)

        tab.textwidget.tag_remove('sel', '1.0', 'end')
        tab.textwidget.tag_add('sel', range.start, range.end)
        tab.textwidget.mark_set('insert', range.start)
        tab.textwidget.see('insert')
        return 'break'

    def on_new_filetab(self, tab: tabs.FileTab) -> None:
        # ButtonRelease because cursor moves when pressing button
        # TODO: virtual events
        tab.textwidget.bind("<Control-ButtonRelease-1>", (lambda event: self.request_jump(tab)), add=True)
        utils.bind_with_data(tab, "<<JumpToDefinitionResponse>>", self.receive_jump, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(Jumper().on_new_filetab)
