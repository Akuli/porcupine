from __future__ import annotations

import dataclasses
import logging
import platform
import sys
import tkinter
import webbrowser
import zlib
from pathlib import Path
from tkinter import ttk
from typing import Any, Dict, Iterator, List, Union
from urllib.parse import quote_plus
from zipfile import ZipFile

import dacite
import yaml
from tree_sitter import Language, Node, Parser, TreeCursor  # type: ignore[import]

from porcupine import dirs, textutils
from porcupine.settings import global_settings

from .base_highlighter import BaseHighlighter

Point = Any
log = logging.getLogger(__name__)

# setup() can show an error message, and the ttk theme affects that
setup_after = ["ttk_themes"]

DATA_DIR = Path(__file__).absolute().with_name("tree-sitter-data")


def show_unsupported_platform_error() -> None:
    global_settings.add_option("show_tree_sitter_platform_error", default=True)
    if not global_settings.get("show_tree_sitter_platform_error", bool):
        return

    window = tkinter.Toplevel()
    window.title("Syntax highlighter error")
    window.resizable(False, False)

    content = ttk.Frame(window, name="content", padding=10)
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)

    label1 = ttk.Label(
        content,
        text=(
            f"Porcupine's syntax highlighter doesn't support {sys.platform} on {platform.machine()} yet."
        ),
        wraplength=600,
        justify="center",
        font="TkHeadingFont",
    )
    label1.pack(pady=5)

    label2 = ttk.Label(
        content,
        text=(
            "You can still use Porcupine."
            + " You will even get syntax highlighting,"
            + " because Porcupine actually has two syntax highlighters."
            + " However, the syntax highlighter to be used as a fallback is slower and more buggy."
            + "\n\nPlease report this by creating an issue on GitHub so that it can be fixed."
        ),
        wraplength=600,
        justify="center",
        font="TkTextFont",
    )
    label2.pack(pady=5)

    var = tkinter.BooleanVar(value=True)
    checkbox = ttk.Checkbutton(content, text="Show this dialog when Porcupine starts", variable=var)
    checkbox.pack(pady=25)

    issue_title = f"Syntax highlighter error: {sys.platform} on {platform.machine()}"
    issue_url = "https://github.com/Akuli/porcupine/issues/new?title=" + quote_plus(issue_title)
    button_frame = ttk.Frame(content)
    button_frame.pack(fill="x")
    ttk.Button(
        button_frame, text="Create a GitHub issue now", command=(lambda: webbrowser.open(issue_url))
    ).pack(side="left", expand=True, fill="x", padx=(0, 10))
    ttk.Button(button_frame, text="Continue to Porcupine", command=window.destroy).pack(
        side="left", expand=True, fill="x", padx=(10, 0)
    )

    window.wait_window()
    global_settings.set("show_tree_sitter_platform_error", var.get())


# https://stackoverflow.com/a/2387880
def compute_crc32(path: Path) -> int:
    crc = 0
    with path.open("rb") as file:
        while True:
            # I tried various chunk sizes, with other things affecting plugin setup time commented out.
            # 128K, 256K and 512K all performed quite well.
            # Smaller and bigger chunks were measurably worse.
            chunk = file.read(256 * 1024)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)  # This is the bottleneck of this plugin's setup() time
    return crc


def prepare_binary() -> Path | None:
    zip_path = DATA_DIR / "tree-sitter-binaries.zip"
    with ZipFile(zip_path) as zipfile:
        try:
            # This must match scripts/build-tree-sitter-binary.py
            extension = {"win32": ".dll", "darwin": ".dylib", "linux": ".so"}[sys.platform]
        except KeyError:
            log.error(f"unsupported platform: sys.platform is {sys.platform!r}")
            show_unsupported_platform_error()
            return None

        binary_filename = f"tree-sitter-binary-{sys.platform}-{platform.machine()}{extension}"
        try:
            info = zipfile.getinfo(binary_filename)
        except KeyError:
            log.error(f"unsupported platform: {binary_filename} not found from {zip_path}")
            show_unsupported_platform_error()
            return None

        # Check if extracted already and not changed since.
        # This way we re-extract after updating Porcupine if necessary.
        binary_path = Path(dirs.user_cache_dir) / binary_filename
        try:
            crc = compute_crc32(binary_path)
        except FileNotFoundError:
            log.warning(f"binary has not been extracted yet, extracting now: {binary_path}")
            zipfile.extract(info, binary_path.parent)
        else:
            if crc != info.CRC:
                log.warning(
                    f"binary has changed after extracting (CRC mismatch), extracting again: {binary_path}"
                )
                zipfile.extract(info, binary_path.parent)
        return binary_path


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
    dont_recurse_inside: List[str]
    token_mapping: Dict[str, Union[str, Dict[str, str]]]


class TreeSitterHighlighter(BaseHighlighter):
    def __init__(self, textwidget: tkinter.Text, binary_path: Path, language_id: str) -> None:
        super().__init__(textwidget)
        self._binary_path = binary_path
        self._language_id = language_id
        self._parser = Parser()
        self._parser.set_language(Language(str(self._binary_path), language_id))
        self._tree = self._parser.parse(self._get_file_content_for_tree_sitter())

        token_mapping_path = DATA_DIR / "token-mappings" / (language_id + ".yml")
        with token_mapping_path.open("r", encoding="utf-8") as file:
            self._config = dacite.from_dict(YmlConfig, yaml.safe_load(file))

    def _get_file_content_for_tree_sitter(self) -> bytes:
        # tk indexes are in chars, tree_sitter is in utf-8 bytes
        # here's my hack to get them compatible:
        #
        # bad:  "örkki" (5 chars) --> b"\xc3\xb6rkki" (6 bytes)
        # good: "örkki" (5 chars) --> b"?rkki" (5 bytes)
        #
        # should be ok as long as all your non-ascii chars are e.g. inside strings
        return self.textwidget.get("1.0", "end - 1 char").encode("ascii", errors="replace")

    # only returns nodes that overlap the start,end range
    def _get_all_nodes(
        self, cursor: TreeCursor, start_point: Point, end_point: Point
    ) -> Iterator[Node]:
        assert self._config is not None
        overlap_start = max(cursor.node.start_point, start_point)
        overlap_end = min(cursor.node.end_point, end_point)
        if overlap_start >= overlap_end:
            # No overlap with the range we care about. Skip subnodes.
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
        start, end = self.get_visible_part()
        start_row, start_col = map(int, start.split("."))
        end_row, end_col = map(int, end.split("."))
        start_point = (start_row - 1, start_col)
        end_point = (end_row - 1, end_col)

        self.delete_tags(start, end)

        for node in self._get_all_nodes(self._tree.walk(), start_point, end_point):
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
            #
            # There's a similar situation in rust: macro name is just an identifier in a macro_invocation
            if (
                self._language_id == "toml"
                and node.type not in ("pair", "comment")
                and node.parent is not None
                and node.parent.type in ("table", "table_array_element")
            ) or (
                self._language_id == "rust"
                and node.type in ("identifier", "scoped_identifier", "!")
                and node.parent is not None
                and node.parent.type == "macro_invocation"
            ):
                type_name = node.parent.type
            else:
                type_name = node.type

            tag_name = self._config.token_mapping.get(type_name, "Token.Text")
            if isinstance(tag_name, dict):
                tag_name = tag_name.get(node.text.decode("utf-8"), "Token.Text")
            assert isinstance(tag_name, str)

            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            self.textwidget.tag_add(
                tag_name, f"{start_row+1}.{start_col}", f"{end_row+1}.{end_col}"
            )

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
