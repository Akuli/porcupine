"""Features for working with Markdown Files.

- Indenting and dedenting lists
"""

from __future__ import annotations

import logging
import re
import tkinter
from functools import partial

from porcupine import get_tab_manager, tabs, textutils, utils

log = logging.getLogger(__name__)


setup_before = ["tabs2spaces", "autoindent"]


def _list_item(line: str) -> re.Match[str] | None:
    """Regex for markdown list item

    1st group is the whitespace (if any) preceding the item
    2nd group is the list item prefix (ex `-`, `+`, `6.`, `#.`)
    3rd group is the item text

    According to:
    - https://spec.commonmark.org/0.30/#lists
    - https://pandoc.org/MANUAL.html#lists
    Technically `#)` is not in either spec, but I won't tell if you won't
    """
    assert isinstance(line, str)
    if not line:
        # empty string
        return None

    assert len(line.splitlines()) == 1

    list_item_regex = re.compile(r"(^[\t ]*)(\d{1,9}[.)]|[-+*]|#\)|#\.) (.*)")
    match = list_item_regex.search(line)
    return match if match else None


def on_tab_key(
    tab: tabs.FileTab, event: tkinter.Event[textutils.MainText], shift_pressed: bool
) -> str | None:
    """Indenting and dedenting list items"""
    if tab.settings.get("filetype_name", object) == "Markdown":
        line = event.widget.get("insert linestart", "insert lineend")
        list_item_status = _list_item(line)

        # shift-tab
        if shift_pressed and list_item_status:
            event.widget.dedent("insert linestart")
            return "break"

        # if it isn't, we want tab to trigger autocomplete instead
        char_before_cursor_is_space = tab.textwidget.get("insert - 1 char", "insert") == " "

        # tab
        if list_item_status and char_before_cursor_is_space:
            event.widget.indent("insert linestart")
            return "break"

    return None


def continue_list(tab: tabs.FileTab, event: tkinter.Event[tkinter.Text]) -> str | None:
    """Automatically continue lists

    This happens after the `autoindent` plugin automatically handles indentation
    """
    if tab.settings.get("filetype_name", object) == "Markdown":
        current_line = event.widget.get("insert - 1l linestart", "insert -1l lineend")
        list_item_match = _list_item(current_line)
        if list_item_match:
            indentation, prefix, item_text = list_item_match.groups()

            tab.textwidget.insert("insert", prefix + " ")
            tab.update()

    return None


def on_enter_press(tab: tabs.FileTab, event: tkinter.Event[tkinter.Text]) -> str | None:
    if tab.settings.get("filetype_name", object) == "Markdown":
        current_line = event.widget.get("insert linestart", "insert lineend")
        list_item_match = _list_item(current_line)
        if list_item_match:
            indentation, prefix, item_text = list_item_match.groups()
            if item_text:
                # there is item text, so we are done here
                return None

            event.widget.delete("insert linestart", "insert lineend")
            return "break"

    return None


def on_new_filetab(tab: tabs.FileTab) -> None:
    utils.bind_tab_key(tab.textwidget, partial(on_tab_key, tab), add=True)
    tab.textwidget.bind("<<post-autoindent>>", partial(continue_list, tab), add=True)
    tab.textwidget.bind("<Return>", partial(on_enter_press, tab), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
