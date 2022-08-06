"""This is Porcupine's syntax highlighting plugin.

This plugin features two syntax highlighters with different advantages and
disadvantages. See filetypes.toml for information about configuring them.

You can change the color theme in Porcupine Settings.
"""

from __future__ import annotations

import logging
import tkinter
from pathlib import Path
from typing import Callable, Any, Iterator, Optional
from pygments import token
from pygments.lexer import LexerMeta

from porcupine import get_tab_manager, tabs, utils
from porcupine.textutils import Changes

from .base_highlighter import BaseHighlighter
from .pygments_highlighter import PygmentsHighlighter
from .tree_sitter_highlighter import TreeSitterConfig, TreeSitterHighlighter, prepare_binary

log = logging.getLogger(__name__)

# Uses tab settings defined in filetypes.toml.
# TODO: what other plugins need this?
setup_after = ["filetypes"]


def _list_all_token_types(tokentype: Any) -> Iterator[Any]:
    yield tokentype
    for sub in map(_list_all_token_types, tokentype.subtypes):
        yield from sub


all_token_tags = set(map(str, _list_all_token_types(token.Token)))


class HighlighterManager:
    def __init__(self, tab: tabs.FileTab, tree_sitter_binary_path: Path | None) -> None:
        self._tab = tab
        self._tree_sitter_binary_path = tree_sitter_binary_path
        self._highlighter: BaseHighlighter | None = None

    def on_config_changed(self, junk: object = None) -> None:
        highlighter_name = self._tab.settings.get("syntax_highlighter", str)
        if highlighter_name == "tree_sitter":
            if self._tree_sitter_binary_path is None:
                log.warning(
                    "using pygments highlighter instead of tree_sitter,"
                    + " because the tree_sitter binary failed to load"
                )
                self._tab.settings.set("syntax_highlighter", "pygments")
                return  # this will be called again soon (or was called again already?)

            self._highlighter = TreeSitterHighlighter(
                self._tab.textwidget,
                self._tree_sitter_binary_path,
                self._tab.settings.get("tree_sitter", TreeSitterConfig),
            )

        else:
            if highlighter_name != "pygments":
                log.warning(
                    f"bad syntax_highlighter setting {repr(highlighter_name)}, assuming 'pygments'"
                )
            self._highlighter = PygmentsHighlighter(
                self._tab.textwidget, self._tab.settings.get("pygments_lexer", LexerMeta)()
            )

        self.update_tags_of_visible_area()

    # Can add some tags outside the range, depending on the highlighter.
    # That's fine, because adding the same tag twice to the same text does nothing.
    def _update_tags(self, start: str, end: str) -> None:
        for tag in all_token_tags:
            self._tab.textwidget.tag_remove(tag, start, end)
        assert self._highlighter is not None
        self._highlighter.add_tags(start, end)

    def update_tags_of_visible_area(self) -> None:
        assert self._highlighter is not None
        start=self._tab.textwidget.index("@0,0")
        end=self._tab.textwidget.index("@0,10000")
        self._update_tags(start,end)

    def update_with_change_event(self, event: utils.EventWithData) -> None:
        assert self._highlighter is not None
        changes = event.data_class(Changes)
        self._highlighter.update_internal_state(changes)

        if len(changes.change_list) == 1 and len(changes.change_list[0].new_text) <= 1:
            # Optimization for typical key strokes (but not for reloading entire file):
            # Only highlight the area that might have changed.
            # TODO: does this surely work correctly if changes[0].new_text == '\n'?
            change = changes.change_list[0]
            start = self._tab.textwidget.index(f"{change.start[0]}.0")
            end = self._tab.textwidget.index(f"{change.end[0]}.0 lineend")
            self._update_tags(start,end)
        else:
            self.update_tags_of_visible_area()


# When scrolling, don't highlight too often. Makes scrolling smoother.
def debounce(
    any_widget: tkinter.Misc, function: Callable[[], None], ms_between_calls_min: int
) -> Callable[[], None]:
    timeout_scheduled = False
    running_requested = False

    def timeout_callback() -> None:
        nonlocal timeout_scheduled, running_requested
        assert timeout_scheduled
        if running_requested:
            function()
            any_widget.after(ms_between_calls_min, timeout_callback)
            running_requested = False
        else:
            timeout_scheduled = False

    def request_running() -> None:
        nonlocal timeout_scheduled, running_requested
        if timeout_scheduled:
            running_requested = True
        else:
            assert not running_requested
            function()
            any_widget.after(ms_between_calls_min, timeout_callback)
            timeout_scheduled = True

    return request_running


def on_new_filetab(tab: tabs.FileTab, tree_sitter_binary_path: Path | None) -> None:
    # pygments_lexer option already exists, as it is used also outside this plugin
    tab.settings.add_option("syntax_highlighter", default="pygments")
    tab.settings.add_option("tree_sitter", default=None, type_=Optional[TreeSitterConfig])

    manager = HighlighterManager(tab, tree_sitter_binary_path)
    tab.bind("<<TabSettingChanged:pygments_lexer>>", manager.on_config_changed, add=True)
    tab.bind("<<TabSettingChanged:syntax_highlighter>>", manager.on_config_changed, add=True)
    tab.bind("<<TabSettingChanged:tree_sitter>>", manager.on_config_changed, add=True)
    manager.on_config_changed()

    # These need lambdas because the highlighter variable can be reassigned.
    utils.bind_with_data(
        tab.textwidget, "<<ContentChanged>>", manager.update_with_change_event, add=True
    )
    utils.add_scroll_command(
        tab.textwidget, "yscrollcommand", debounce(tab, manager.update_tags_of_visible_area, 100)
    )


def setup() -> None:
    tree_sitter_binary_path = prepare_binary()
    get_tab_manager().add_filetab_callback(lambda tab: on_new_filetab(tab, tree_sitter_binary_path))
