"""This is Porcupine's syntax highlighting plugin.

This plugin features two syntax highlighters with different advantages and
disadvantages. See filetypes.toml for information about configuring them.

You can change the color theme in Porcupine Settings.
"""

from __future__ import annotations

import logging
import tkinter
from pathlib import Path
from typing import Callable, Optional
from pygments.lexer import LexerMeta

from porcupine import get_tab_manager, tabs, textutils,utils

from .base_highlighter import BaseHighlighter
from .pygments_highlighter import PygmentsHighlighter
from .tree_sitter_highlighter import TreeSitterConfig, TreeSitterHighlighter, prepare_binary

log = logging.getLogger(__name__)

# Uses tab settings defined in filetypes.toml.
# TODO: what other plugins need this?
setup_after = ["filetypes"]


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

            config = self._tab.settings.get("tree_sitter", TreeSitterConfig)
            log.info(f"creating a tree_sitter highlighter with language {config.language_name}")
            self._highlighter = TreeSitterHighlighter(
                self._tab.textwidget,
                self._tree_sitter_binary_path,
                config,
            )

        else:
            if highlighter_name != "pygments":
                log.warning(
                    f"bad syntax_highlighter setting {repr(highlighter_name)}, assuming 'pygments'"
                )

            lexer_class = self._tab.settings.get("pygments_lexer", LexerMeta)
            log.info(f"creating a pygments highlighter with lexer class {lexer_class}")
            self._highlighter = PygmentsHighlighter(
                self._tab.textwidget, lexer_class()
            )

        self._highlighter.on_scroll()

    def on_change_event(self, event: utils.EventWithData) -> None:
        assert self._highlighter is not None
        self._highlighter.on_change(event.data_class(textutils.Changes))

    def on_scroll_event(self)->None:
        assert self._highlighter is not None
        self._highlighter.on_scroll()


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
        tab.textwidget, "<<ContentChanged>>", manager.on_change_event, add=True
    )
    utils.add_scroll_command(
        tab.textwidget, "yscrollcommand", debounce(tab, manager.on_scroll_event, 100)
    )


def setup() -> None:
    tree_sitter_binary_path = prepare_binary()
    get_tab_manager().add_filetab_callback(lambda tab: on_new_filetab(tab, tree_sitter_binary_path))
