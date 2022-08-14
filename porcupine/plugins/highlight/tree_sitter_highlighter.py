from __future__ import annotations

import dataclasses
import logging
import re
import sys
import tkinter
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterator, List, Union

import dacite
import yaml

from porcupine import textutils

from .base_highlighter import BaseHighlighter

# TODO: how to install tree-sitter and tree-sitter-languages on Windows?
if sys.platform != "win32" or TYPE_CHECKING:
    import tree_sitter  # type: ignore[import]
    import tree_sitter_languages  # type: ignore[import]

log = logging.getLogger(__name__)

# setup() can show an error message, and the ttk theme affects that
setup_after = ["ttk_themes"]

TOKEN_MAPPING_DIR = Path(__file__).absolute().with_name("tree-sitter-token-mappings")


# DONT_LOOK_INSIDE = [
#    # don't recurse inside strings, for now
#    "string_literal",  # c string
#    "char_literal",  # c character
#    # in markdown, everything's ultimately Text, but not if we don't recurse that deep
#    "fenced_code_block",
#    "code_span",
#    "link_destination",
#    "emphasis",
#    "strong_emphasis",
# ]
#
#
# def get_tag_name(node) -> str:
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


@dataclasses.dataclass
class YmlConfig:
    token_mapping: Dict[str, Union[str, Dict[str, str]]]
    dont_recurse_inside: List[str] = dataclasses.field(default_factory=list)
    queries: Dict[str, str] = dataclasses.field(default_factory=dict)


def _strip_comments(tree_sitter_query: str) -> str:
    return re.sub(r"#.*", "", tree_sitter_query)


class TreeSitterHighlighter(BaseHighlighter):
    def __init__(self, textwidget: tkinter.Text, language_name: str) -> None:
        super().__init__(textwidget)
        self._language = tree_sitter_languages.get_language(language_name)

        self._parser = tree_sitter.Parser()
        self._parser.set_language(self._language)
        self._tree = self._parser.parse(self._get_file_content_for_tree_sitter())

        token_mapping_path = TOKEN_MAPPING_DIR / (language_name + ".yml")
        with token_mapping_path.open("r", encoding="utf-8") as file:
            self._config = dacite.from_dict(YmlConfig, yaml.safe_load(file))

        # Pseudo-optimization: "pre-compile" queries when the highlighter starts.
        # Also makes the highlighter fail noticably if any query contain syntax errors.
        self._queries = {
            node_type_name: self._language.query(_strip_comments(text))
            for node_type_name, text in self._config.queries.items()
        }

    def _get_file_content_for_tree_sitter(self) -> bytes:
        # tk indexes are in chars, tree_sitter is in utf-8 bytes
        # here's my hack to get them compatible:
        #
        # bad:  "örkki" (5 chars) --> b"\xc3\xb6rkki" (6 bytes)
        # good: "örkki" (5 chars) --> b"?rkki" (5 bytes)
        #
        # should be ok as long as all your non-ascii chars are e.g. inside strings
        return self.textwidget.get("1.0", "end - 1 char").encode("ascii", errors="replace")

    def _decide_tag(self, node: tree_sitter.Node) -> str:
        # A hack for TOML. This:
        #
        #   [foo]
        #   x=1
        #   y=2
        #
        # parses as:
        #
        #    type='[' text=b'['
        #    type='bare_key' text=b'foo'
        #    type=']' text=b']'
        #    type='pair' text=b'x=1'
        #    type='pair' text=b'y=2'
        #
        # I want the whole section header [foo] to have the same tag.
        if (
            self._language.name == "toml"
            and node.type not in ("pair", "comment")
            and node.parent is not None
            and node.parent.type in ("table", "table_array_element")
        ):
            type_name = node.parent.type
        else:
            type_name = node.type

        if set(type_name) <= set("+-*/%~&|^!?<>=@.,:;()[]{}"):
            default = "Token.Operator"
        else:
            default = "Token.Text"

        config_value = self._config.token_mapping.get(type_name, default)
        if isinstance(config_value, dict):
            return config_value.get(node.text.decode("utf-8"), default)
        return config_value

    # only returns nodes that overlap the start,end range
    def _get_nodes_and_tags(
        self,
        cursor: tree_sitter.TreeCursor,
        start_point: tuple[int, int],
        end_point: tuple[int, int],
    ) -> Iterator[tuple[tree_sitter.Node, str]]:
        assert self._config is not None
        overlap_start = max(cursor.node.start_point, start_point)
        overlap_end = min(cursor.node.end_point, end_point)
        if overlap_start >= overlap_end:
            # No overlap with the range we care about. Skip subnodes.
            return

        query = self._queries.get(cursor.node.type)
        if query is not None:
            to_recurse = []
            for subnode, tag_or_recurse in query.captures(cursor.node):
                if tag_or_recurse == "recurse":
                    to_recurse.append(subnode)
                else:
                    yield (subnode, tag_or_recurse)

            for subnode in to_recurse:
                # Tell the tagging code that we're about to recurse.
                # This lets it wipe tags that were previously added on the area.
                # That's also why recursing is done last.
                yield (subnode, "recurse")
                yield from self._get_nodes_and_tags(subnode.walk(), start_point, end_point)
            return

        if cursor.node.type not in self._config.dont_recurse_inside and cursor.goto_first_child():
            yield from self._get_nodes_and_tags(cursor, start_point, end_point)
            while cursor.goto_next_sibling():
                yield from self._get_nodes_and_tags(cursor, start_point, end_point)
            cursor.goto_parent()
        else:
            yield (cursor.node, self._decide_tag(cursor.node))

    # tree-sitter has get_changed_ranges() method, but it has a couple problems:
    #   - It returns empty list if you append text to end of a line. But text like that may need to
    #     get highlighted.
    #   - Release version from pypi doesn't have the method.
    def update_tags_of_visible_area_from_tree(self) -> None:
        start, end = self.get_visible_part()
        start_row, start_col = map(int, start.split("."))
        end_row, end_col = map(int, end.split("."))
        start_point = (start_row - 1, start_col)
        end_point = (end_row - 1, end_col)

        self.delete_tags(start, end)

        for node, tag in self._get_nodes_and_tags(self._tree.walk(), start_point, end_point):
            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            start = f"{start_row+1}.{start_col}"
            end = f"{end_row+1}.{end_col}"

            if tag == "recurse":
                self.delete_tags(start, end)
            else:
                self.textwidget.tag_add(tag, start, end)

    def on_scroll(self) -> None:
        # TODO: This could be optimized. Often most of the new visible part was already visible before.
        self.update_tags_of_visible_area_from_tree()

    def on_change(self, changes: textutils.Changes) -> None:
        if not changes.change_list:
            return

        if len(changes.change_list) >= 2:
            # slow, but doesn't happen very often in normal editing
            self._tree = self._parser.parse(self._get_file_content_for_tree_sitter())
        else:
            [change] = changes.change_list
            start_row, start_col = change.start
            old_end_row, old_end_col = change.end
            new_end_row = start_row + change.new_text.count("\n")
            if "\n" in change.new_text:
                new_end_col = len(change.new_text.split("\n")[-1])
            else:
                new_end_col = start_col + len(change.new_text)

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
            self._tree = self._parser.parse(self._get_file_content_for_tree_sitter(), self._tree)

        self.update_tags_of_visible_area_from_tree()
