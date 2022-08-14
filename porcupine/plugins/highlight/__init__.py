"""This is Porcupine's syntax highlighting plugin.

This plugin features two syntax highlighters with different advantages and
disadvantages. See filetypes.toml for information about configuring them.

You can change the color theme in Porcupine Settings.
"""

from __future__ import annotations

import logging
import sys
import tkinter
from typing import Callable, Optional

from pygments.lexer import LexerMeta

from porcupine import get_tab_manager, tabs, textutils, utils

from .base_highlighter import BaseHighlighter
from .pygments_highlighter import PygmentsHighlighter
from .tree_sitter_highlighter import TreeSitterHighlighter

log = logging.getLogger(__name__)

# Uses tab settings defined in filetypes.toml.
# TODO: what other plugins need this?
setup_after = ["filetypes"]


class HighlighterManager:
    def __init__(self, tab: tabs.FileTab) -> None:
        self._tab = tab
        self._highlighter: BaseHighlighter | None = None

    def on_config_changed(self, junk: object = None) -> None:
        highlighter_name = self._tab.settings.get("syntax_highlighter", str)

        if highlighter_name == "tree_sitter" and sys.platform == "win32":
            log.warning(
                "the tree_sitter syntax highlighter is not supported on Windows yet,"
                + " falling back to the pygments highlighter"
            )
            self._tab.settings.set("syntax_highlighter", "pygments")  # runs this again
            return

        if highlighter_name == "tree_sitter":
            language_name = self._tab.settings.get("tree_sitter_language_name", Optional[str])
            if language_name is None:
                # TODO: set all highlighter settings at once, so that this doesn't happen in the
                # middle of applying filetype settings
                log.info("highlighter_name set to 'tree_sitter' even though tree_sitter_language_name is unset")
                return
            log.info(f"creating a tree_sitter highlighter with language {repr(language_name)}")
            self._highlighter = TreeSitterHighlighter(self._tab.textwidget, language_name)
        elif highlighter_name == "pygments":
            lexer_class = self._tab.settings.get("pygments_lexer", LexerMeta)
            log.info(f"creating a pygments highlighter with lexer class {lexer_class}")
            self._highlighter = PygmentsHighlighter(self._tab.textwidget, lexer_class())
        else:
            log.warning(
                f"bad syntax_highlighter setting {repr(highlighter_name)}, assuming 'pygments'"
            )
            self._tab.settings.set("syntax_highlighter", "pygments")  # runs this again
            return

        self._highlighter.on_scroll()

    def on_change_event(self, event: utils.EventWithData) -> None:
        assert self._highlighter is not None
        self._highlighter.on_change(event.data_class(textutils.Changes))

    def on_scroll_event(self) -> None:
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


def on_new_filetab(tab: tabs.FileTab) -> None:
    # pygments_lexer option already exists, as it is used also outside this plugin
    tab.settings.add_option("syntax_highlighter", default="pygments")
    tab.settings.add_option("tree_sitter_language_name", default=None, type_=Optional[str])

    manager = HighlighterManager(tab)
    tab.bind("<<TabSettingChanged:pygments_lexer>>", manager.on_config_changed, add=True)
    tab.bind("<<TabSettingChanged:syntax_highlighter>>", manager.on_config_changed, add=True)
    tab.bind("<<TabSettingChanged:tree_sitter_language_name>>", manager.on_config_changed, add=True)
    manager.on_config_changed()

    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", manager.on_change_event, add=True)
    utils.add_scroll_command(
        tab.textwidget, "yscrollcommand", debounce(tab, manager.on_scroll_event, 100)
    )


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
