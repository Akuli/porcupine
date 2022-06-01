# TODO: test more languages: c++, java, javascript, html, css, php, shell, anything else??
# TODO: test large files
# TODO: offsets are in utf8 bytes, so ä currently messes up everything after on same line
# TODO: integrate compile step, aka build.py, to editor
# TODO: docs for config file stuff
# TODO: recurse inside strings? showing f-string contents properly would be nice
# TODO: "big files = slow" issue not entirely highlighter's fault, try mypy/checker.py with highlighter disabled
# TODO: tree-sitter segfault: install from github with pip, import in >>> prompt, Ctrl+D
from __future__ import annotations

import dataclasses
import logging
import tkinter
from typing import Optional, Callable, Any, Dict,List,Iterator

from tree_sitter import Language, Parser, Tree,TreeCursor,Node # type: ignore[import]

from porcupine import get_tab_manager, tabs, textutils, utils
from porcupine.plugins.pygments_highlight import all_token_tags

Point = Any
log = logging.getLogger(__name__)


DONT_LOOK_INSIDE = [
    # don't recurse inside strings, for now
    "string_literal",  # c string
    "char_literal",  # c character
    "quoted_key",  # string in toml section header
    # in markdown, everything's ultimately Text, but not if we don't recurse that deep
    "fenced_code_block",
    "code_span",
    "link_destination",
    "emphasis",
    "strong_emphasis",
]


#def get_tag_name(node) -> str:
#    # Programming languages
#    if node.type == "identifier":  # variable names
#        return "Token.Name"
#    if node.type == "type_identifier":  # typedef names in C
#        return "Token.Name.Class"
#    if node.type == "field_identifier":  # struct members in C when they're used
#        return "Token.Name.Attribute"
#    if node.type == "comment":
#        return "Token.Comment"
#    if node.type == "integer":
#        return "Token.Literal.Number.Integer"
#    if node.type == "float":
#        return "Token.Literal.Number.Float"
#    if node.type == "number_literal":
#        return "Token.Literal.Number"
#    # system_lib_string is the <foo.h> includes in c/c++
#    if node.type in ("string", "string_literal", "char_literal", "system_lib_string"):
#        return "Token.Literal.String"
#
#    # Markdown
#    if node.type == "text":
#        return "Token.Text"
#    if node.type == "emphasis":  # *italic* text in markdown
#        return "Token.Comment"
#    if node.type == "strong_emphasis":  # **bold** text in markdown
#        return "Token.Keyword"
#    if node.type in ("fenced_code_block", "code_span"):
#        return "Token.Literal.String"
#
#    # TOML
#    if node.type == "quoted_key":
#        return "Token.Literal.String"
#
#    # Fallbacks for programming languages, e.g. python has "(" and "def" nodes
#    elif node.type.isidentifier():
#        return "Token.Keyword"
#    else:
#        return "Token.Operator"
#

@dataclasses.dataclass
class Config:
    language_name: str
    dont_recurse_inside: List[str]
    token_mapping: Dict[str, str]


class Highlighter:
    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)
        self._config: Config | None = None
        self._parser: Parser | None = None
        self._tree: Tree | None = None

    # only returns nodes that overlap the start,end range
    def _get_all_nodes(self, cursor: TreeCursor, start_point:Point, end_point:Point) -> Iterator[Node]:
        assert self._config is not None
        overlap_start = max(cursor.node.start_point, start_point)
        overlap_end = min(cursor.node.end_point, end_point)
        if overlap_start >= overlap_end:
            return

        if cursor.node.type not in self._config.dont_recurse_inside and cursor.goto_first_child():
            yield from self._get_all_nodes(cursor, start_point, end_point)
            while cursor.goto_next_sibling():
                yield from self._get_all_nodes(cursor, start_point, end_point)
            cursor.goto_parent()
        else:
            yield cursor.node

    # tree-sitter has get_changed_ranges() method, but it has a couple problems:
    #   - It returns empty list if you append text to end of a line. But text like that may need to
    #     get highlighted.
    #   - Release version from pypi doesn't have the method.
    def update_tags_of_visible_area_from_tree(self) -> None:
        if self._config is None:
            return

        log.debug("Updating colors of visible part of file")
        start = self.textwidget.index("@0,0")
        end = self.textwidget.index("@0,10000")
        start_row, start_col = map(int, start.split("."))
        end_row, end_col = map(int, end.split("."))
        start_point = (start_row - 1, start_col)
        end_point = (end_row - 1, end_col)

        for tag in all_token_tags:
            self.textwidget.tag_remove(tag, start, end)

        assert self._tree is not None
        for node in list(self._get_all_nodes(self._tree.walk(), start_point, end_point)):
            try:
                tag_name = self._config.token_mapping[node.type]
            except KeyError:
                try:
                    tag_name = self._config.token_mapping[f"{node.type}[{node.text.decode('utf-8')}]"]
                except KeyError:
                    tag_name = self._config.token_mapping["anything_else"]
            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            self.textwidget.tag_add(
                tag_name, f"{start_row+1}.{start_col}", f"{end_row+1}.{end_col}"
            )

    def reparse_whole_file(self) -> None:
        log.info("Reparsing the whole file from scratch")
        if self._parser is None:
            self._tree = None
        else:
            self._tree = self._parser.parse(self.textwidget.get("1.0", "end - 1 char").encode("utf-8"))

    def set_config(self, config: Config | None) -> None:
        print("tree_sitter set language", None if config is None else config.language_name)
        # TODO: better error handling than assert / KeyError
        log.info(f"Changing language: {None if config is None else config.language_name}")
        self._config = config
        if config is None:
            self._parser = None
        else:
            assert "anything_else" in config.token_mapping
            for token_tag in config.token_mapping.values():
                assert token_tag in all_token_tags, token_tag
            self._parser = Parser()
            # TODO: load this at import time, and check in pygments plugin if this plugin imported successfully
            self._parser.set_language(Language("build/langs.so", config.language_name))

        self.reparse_whole_file()
        self.update_tags_of_visible_area_from_tree()

    def on_change(self, event: utils.EventWithData) -> None:
        if self._tree is None or self._parser is None:
            return

        change_list = event.data_class(textutils.Changes).change_list
        if not change_list:
            return

        if len(change_list) >= 2:
            # doesn't happen very often in normal editing
            self.reparse_whole_file()
        else:
            [change] = change_list
            # FIXME: bytes are wrong when text has non-ascii chars
            start_row, start_col = change.start
            old_end_row, old_end_col = change.end
            new_end_row = start_row + change.new_text.count("\n")
            if "\n" in change.new_text:
                new_end_col = len(change.new_text.split("\n")[-1])
            else:
                new_end_col = start_col + len(change.new_text)

            log.debug(
                f"File changed between {start_row}.{start_col} and {new_end_row}.{new_end_col}, updating"
            )

            start_byte = self.textwidget.tk.call(
                str(self.textwidget), "count", "-chars", "1.0", f"{start_row}.{start_col}"
            )
            self._tree.edit(
                start_byte=start_byte,
                old_end_byte=start_byte + change.old_text_len,
                new_end_byte=start_byte + len(change.new_text),
                start_point=(start_row - 1, start_col),
                old_end_point=(old_end_row - 1, old_end_col),
                new_end_point=(new_end_row - 1, new_end_col),
            )
            self._tree = self._parser.parse(
                self.textwidget.get("1.0", "end - 1 char").encode("utf-8"), self._tree
            )

        self.update_tags_of_visible_area_from_tree()


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
    tab.settings.add_option("tree_sitter", default=None, type_=Optional[Config])

    def on_config_changed(junk: object = None) -> None:
        highlighter.set_config(tab.settings.get("tree_sitter", Optional[Config]))

    highlighter = Highlighter(tab.textwidget)
    tab.bind("<<TabSettingChanged:tree_sitter>>", on_config_changed, add=True)
    on_config_changed()
    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", highlighter.on_change, add=True)
    utils.add_scroll_command(
        tab.textwidget,
        "yscrollcommand",
        debounce(tab, highlighter.update_tags_of_visible_area_from_tree, 100),
    )

    highlighter.reparse_whole_file()
    highlighter.update_tags_of_visible_area_from_tree()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
