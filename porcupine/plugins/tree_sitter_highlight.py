"""Syntax highlighting.

This plugin only highlights file types that have syntax_highlighter set to
"tree_sitter" in filetypes.toml.
"""

from __future__ import annotations

import dataclasses
import webbrowser
import logging
import platform
import reprlib
import sys
import tkinter
import zlib
from functools import partial
from pathlib import Path
from tkinter import ttk
from urllib.parse import quote_plus
from typing import Any, Callable, Dict, Iterator, List, Optional, Union
from zipfile import ZipFile

from tree_sitter import Language, Node, Parser, Tree, TreeCursor  # type: ignore[import]

from porcupine import dirs, get_tab_manager, tabs, textutils, utils
from porcupine.settings import global_settings
from porcupine.plugins.pygments_highlight import all_token_tags

Point = Any
log = logging.getLogger(__name__)

# setup() can show an error message, and the ttk theme affects that
setup_after = ["ttk_themes"]


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


def prepare_binary() -> Path | None:
    zip_path = Path(__file__).absolute().with_name("tree-sitter-binaries.zip")
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
                    f"binary has changed after extracting (CRC mismatch), extracting again: {binary_filename}"
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
class Config:
    language_name: str
    dont_recurse_inside: List[str]
    token_mapping: Dict[str, Union[str, Dict[str, str]]]


class Highlighter:
    def __init__(self, binary_path: Path, textwidget: tkinter.Text) -> None:
        self._binary_path = binary_path
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)
        self._config: Config | None = None
        self._parser: Parser | None = None
        self._tree: Tree | None = None

    # only returns nodes that overlap the start,end range
    def _get_all_nodes(
        self, cursor: TreeCursor, start_point: Point, end_point: Point
    ) -> Iterator[Node]:
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
                self._config.language_name == "toml"
                and node.type not in ("pair", "comment")
                and node.parent is not None
                and node.parent.type in ("table", "table_array_element")
            ) or (
                self._config.language_name == "rust"
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

    def _get_file_content_for_tree_sitter(self) -> bytes:
        # tk indexes are in chars, tree_sitter is in utf-8 bytes
        # here's my hack to get them compatible:
        #
        # bad:  "örkki" (5 chars) --> b"\xc3\xb6rkki" (6 bytes)
        # good: "örkki" (5 chars) --> b"?rkki" (5 bytes)
        #
        # should be ok as long as all your non-ascii chars are e.g. inside strings
        return self.textwidget.get("1.0", "end - 1 char").encode("ascii", errors="replace")

    def recreate_the_whole_tree(self) -> None:
        log.info("Reparsing the whole file from scratch")
        if self._parser is None:
            self._tree = None
        else:
            self._tree = self._parser.parse(self._get_file_content_for_tree_sitter())

    def set_config(self, config: Config | None) -> None:
        log.info(f"Changing language: {None if config is None else config.language_name}")
        self._config = config
        if config is None:
            self._parser = None
        else:
            self._parser = Parser()
            self._parser.set_language(Language(self._binary_path, config.language_name))

        self.recreate_the_whole_tree()
        self.update_tags_of_visible_area_from_tree()

    def update_based_on_changes(self, event: utils.EventWithData) -> None:
        if self._tree is None or self._parser is None:
            return

        change_list = event.data_class(textutils.Changes).change_list
        if not change_list:
            return

        if len(change_list) >= 2:
            # doesn't happen very often in normal editing
            self.recreate_the_whole_tree()
        else:
            [change] = change_list
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
            self._tree = self._parser.parse(self._get_file_content_for_tree_sitter(), self._tree)

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


def on_new_filetab(binary_path: Path | None, tab: tabs.FileTab) -> None:
    tab.settings.add_option("syntax_highlighter", default="pygments", exist_ok=True)

    if binary_path is None:

        def delegate_to_pygments(junk: object = None) -> None:
            if tab.settings.get("syntax_highlighter", str) == "tree_sitter":
                log.warning("Delegating to pygments highlighter")
                tab.settings.set("syntax_highlighter", "pygments")

        tab.bind("<<TabSettingChanged:syntax_highlighter>>", delegate_to_pygments, add=True)
        delegate_to_pygments()
        return

    tab.settings.add_option("tree_sitter", default=None, type_=Optional[Config])

    def on_config_changed(junk: object = None) -> None:
        if tab.settings.get("syntax_highlighter", str) == "tree_sitter":
            highlighter.set_config(tab.settings.get("tree_sitter", Config))
        else:
            highlighter.set_config(None)

    highlighter = Highlighter(binary_path, tab.textwidget)
    tab.bind("<<TabSettingChanged:syntax_highlighter>>", on_config_changed, add=True)
    tab.bind("<<TabSettingChanged:tree_sitter>>", on_config_changed, add=True)
    on_config_changed()

    utils.bind_with_data(
        tab.textwidget, "<<ContentChanged>>", highlighter.update_based_on_changes, add=True
    )
    utils.add_scroll_command(
        tab.textwidget,
        "yscrollcommand",
        debounce(tab, highlighter.update_tags_of_visible_area_from_tree, 100),
    )

    highlighter.recreate_the_whole_tree()
    highlighter.update_tags_of_visible_area_from_tree()


def setup() -> None:
    binary_path = prepare_binary()
    get_tab_manager().add_filetab_callback(partial(on_new_filetab, binary_path))


# A small command-line utility for configuring tree-sitter.
# Documented in default_filetypes.toml.
def tree_dumping_command_line_util() -> None:
    [program_name, language_name, filename] = sys.argv

    def show_nodes(cursor: TreeCursor, indent_level: int = 0) -> None:
        node = cursor.node
        print(
            f"{'  ' * indent_level}type={node.type} text={reprlib.repr(node.text.decode('utf-8'))}"
        )

        if cursor.goto_first_child():
            show_nodes(cursor, indent_level + 1)
            while cursor.goto_next_sibling():
                show_nodes(cursor, indent_level + 1)
            cursor.goto_parent()

    binary_path = prepare_binary()
    assert binary_path is not None

    parser = Parser()
    parser.set_language(Language(binary_path, language_name))
    tree = parser.parse(open(filename, "rb").read())
    show_nodes(tree.walk())


if __name__ == "__main__":
    tree_dumping_command_line_util()
