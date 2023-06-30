"""If configuration says so, insert spaces when the tab key is pressed."""

from __future__ import annotations

import logging
import re
import tkinter
from functools import partial

from porcupine import get_tab_manager, tabs, textutils, utils

log = logging.getLogger(__name__)


setup_before = ["tabs2spaces"]


def _is_list_item(line: str) -> bool:
    """Detect if the line that is passed is a markdown list item

    According to:
    - https://spec.commonmark.org/0.30/#lists
    - https://pandoc.org/MANUAL.html#lists
    """
    assert len(line.splitlines()) == 1
    pattern = r"^\s*\d{1,9}[.)]|^\s*[-+*]|^\s*#\)|^\s*#\."
    regex = re.compile(pattern)
    match = regex.search(line)
    return bool(match)


def on_tab_key(
    tab: tabs.FileTab,
    event: tkinter.Event[textutils.MainText],
    shift_pressed: bool,
) -> str:
    """Indenting and dedenting list items"""
    if tab.settings.get("filetype_name", str) == "Markdown":
        line = event.widget.get("insert linestart", "insert lineend")
        list_item_status = _is_list_item(line)

        if shift_pressed and list_item_status:
            event.widget.dedent("insert linestart")
            return "break"

        if list_item_status:
            event.widget.indent("insert linestart")
            return "break"


def on_new_filetab(tab: tabs.FileTab) -> None:
    utils.bind_tab_key(tab.textwidget, partial(on_tab_key, tab), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
