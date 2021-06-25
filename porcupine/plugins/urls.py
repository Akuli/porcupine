"""Find URLs in code and make them clickable."""
from __future__ import annotations

import tkinter
import webbrowser
from functools import partial
from typing import Iterable, Tuple

from porcupine import get_tab_manager, tabs, utils
from porcupine.plugins import underlines


def find_urls(text: tkinter.Text, start: str, end: str) -> Iterable[Tuple[str, str]]:
    match_ends_and_search_begins = start
    while True:
        match_start = text.search(
            r"\mhttps?://[a-z]", match_ends_and_search_begins, end, nocase=True, regexp=True
        )
        if not match_start:  # empty string means not found
            break

        url = text.get(match_start, f"{match_start} lineend")
        before_url = (
            None if text.index(match_start) == "1.0" else text.get(f"{match_start} - 1 char")
        )

        # urls end on space or quote
        url = url.split(" ")[0]
        url = url.split("'")[0]
        url = url.split('"')[0]

        open2close = {"(": ")", "{": "}", "<": ">"}
        close2open = {")": "(", "}": "{", ">": "<"}

        if before_url in open2close and open2close[before_url] in url:
            # url is parenthesized
            url = url.split(open2close[before_url])[0]
        if url[-1] in close2open and close2open[url[-1]] not in url:
            # url isn't like "Bla(bla)" but ends with ")" or similar, assume that's not part of url
            url = url[:-1]

        # urls in middle of text: URL, and URL.
        url = url.rstrip(".,")

        match_ends_and_search_begins = f"{match_start} + {len(url)} chars"
        yield (match_start, match_ends_and_search_begins)


def update_url_underlines(tab: tabs.FileTab, junk: object = None) -> None:
    view_start = tab.textwidget.index("@0,0")
    view_end = tab.textwidget.index("@0,10000")
    shortcut1 = utils.get_binding("<<Urls:OpenWithMouse>>")
    shortcut2 = utils.get_binding("<<Urls:OpenWithKeyboard>>")

    tab.event_generate(
        "<<SetUnderlines>>",
        data=underlines.Underlines(
            id="urls",
            underline_list=[
                underlines.Underline(start, end, f"{shortcut1} or {shortcut2} to open")
                for start, end in find_urls(tab.textwidget, view_start, view_end)
            ],
        ),
    )


def open_the_url(tab: tabs.FileTab, index: str, junk: object) -> str | None:
    # tag_ranges is a painful method to use
    ranges = tab.textwidget.tag_ranges("underline:urls")
    for start, end in zip(ranges[0::2], ranges[1::2]):
        if tab.textwidget.compare(start, "<=", index) and tab.textwidget.compare(index, "<=", end):
            webbrowser.open(tab.textwidget.get(start, end))
            return "break"
    return None


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.textwidget.bind("<<ContentChanged>>", partial(update_url_underlines, tab), add=True)
    utils.add_scroll_command(tab.textwidget, "yscrollcommand", partial(update_url_underlines, tab))
    update_url_underlines(tab)

    tab.textwidget.tag_bind(
        "underline:urls", "<<Urls:OpenWithMouse>>", partial(open_the_url, tab, "current"), add=True
    )
    tab.textwidget.bind("<<Urls:OpenWithKeyboard>>", partial(open_the_url, tab, "insert"), add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
