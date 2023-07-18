from __future__ import annotations

import re, sys, os, subprocess
import tempfile
import tkinter
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator
import webbrowser

import marko
from marko import block, inline

if TYPE_CHECKING:
    from .widget import MarkdownPreviewWidget

INDENT_SPACES = 4


class Reference:
    def __init__(self, dest: str) -> None:
        self.dest = dest


class URL(Reference):
    def open(self, widget):
        webbrowser.open(self.dest)


class File(Reference):
    def open(self, widget):
        path = widget.path.parent / self.dest

        if not path.exists():
            return
        if not path.is_dir():
            # TODO: maybe show a warning, because this can execute files?
            ...

        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class Anchor(Reference):
    def open(self, widget):
        widget.tag_remove("highlight", "0.0", "end")
        for tag in tuple(f"heading_{i}" for i in range(1, 7)):
            ranges = widget.tag_ranges(tag)
            for start, end in zip(ranges[0::2], ranges[1::2]):
                if self.dest[1:].lower() in widget.get(start, end).replace(" ", "-").lower():
                    widget.tag_add("highlight", start, end)
                    widget.see(start)
                    return


class Footnote(Reference):
    def open(self, widget):
        ...


class MarkupPreviewRenderer:
    current_tags: set[str] = set()
    images: dict[str, tkinter.PhotoImage] = {}

    def __init__(self, widget: MarkdownPreviewWidget):
        self.indent = ""
        self.widget = widget
        self.footnotes = {}
        self.links: dict[str, Reference] = {}

    @contextmanager
    def indented(self, spaces: int) -> Generator[None, None, None]:
        old_indent = self.indent
        self.indent += " " * spaces
        yield
        self.indent = old_indent

    @contextmanager
    def tagged(self, *tags: str) -> Generator[None, None, None]:
        self.current_tags.update(tags)
        yield
        self.current_tags.difference_update(tags)

    def clear(self):
        self.links.clear()
        self.footnotes.clear()

    def insert(self, string: str) -> None:
        tags = tuple(self.current_tags)
        if string == "\n":
            tags = tags + ("nospacing",)
        self.widget.insert("end - 1 char", string, tags)

    # Renderer methods

    def render(self, element: Element) -> Any:
        if hasattr(element, "get_type"):
            func_name = "render_" + element.get_type(snake_case=True)
            render_func = getattr(self, func_name, None)
            if render_func is not None:
                return render_func(element)
        return self.render_children(element)

    def render_children(self, element: Any) -> Any:
        for child in element.children:
            self.render(child)  # type: ignore

    def render_document(self, node):
        self.render_children(node)
        with self.tagged("footnote"):
            for i in self.footnotes.values():
                self.insert(f"{i.label}.  ")
                self.render_children(i)

    def render_heading(self, element: marko.block.Heading | marko.block.SetextHeading) -> None:
        with self.tagged(f"heading_{element.level}"):
            self.render_children(element)

        self.insert("\n")

    render_setext_heading = render_heading

    def render_paragraph(self, element: marko.block.Paragraph) -> None:
        self.render_children(element)
        self.insert("\n")

    def render_literal(self, element: marko.inline.Literal) -> None:
        assert isinstance(element.children, str)
        self.insert(element.children)

    def render_raw_text(self, element: marko.inline.RawText) -> None:
        self.insert(element.children)

    def render_line_break(self, element: marko.inline.LineBreak) -> None:
        self.insert(" " if element.soft else "\n")

    def font_measure(self, string: str) -> int:
        # because I won't create a tkinter.font.Font just for this
        return int(self.widget.tk.call("font", "measure", self.widget.cget("font"), string))

    def render_list(self, element: marko.block.List) -> None:
        bullet = "\u2022" if len(self.indent) < INDENT_SPACES else "\u25E6"
        tag = f"list_item_{len(self.indent) + INDENT_SPACES}"

        with self.indented(INDENT_SPACES), self.tagged(tag):
            indent = self.font_measure(f"{self.indent}{bullet}  ")
            self.widget.tag_config(tag, spacing1=2, spacing3=2, lmargin2=indent + 1)

            if element.ordered:
                for num, child in enumerate(element.children, start=element.start):
                    self.insert(f"{self.indent}{num}.  ")
                    self.render(child)
            else:
                for child in element.children:
                    self.insert(f"{self.indent}{bullet}  ")
                    self.render(child)

    def render_list_item(self, element: marko.block.ListItem) -> None:
        self.render_children(element)

    def render_footnote_ref(self, element: marko.block.ListItem) -> None:
        with self.tagged("upper_index", "link"):
            self.links[self.widget.index("end - 1 char")] = Footnote(element.label)
            self.insert(f"[{element.label}]")

    def render_footnote_def(self, element: marko.block.ListItem) -> None:
        self.footnotes[self.widget.index("end - 1 char")] = element

    def render_quote(self, element: marko.block.Quote) -> None:
        with self.tagged("quote"):
            self.render_children(element)

    def render_code_span(self, element: marko.inline.CodeSpan) -> None:
        assert isinstance(element.children, str)
        with self.tagged("code_span"):
            self.insert(element.children)

    def render_code_block(self, element: marko.block.CodeBlock | marko.block.FencedCode) -> None:
        with self.tagged("code_block"):
            self.render_children(element)

    render_fenced_code = render_code_block

    def render_emphasis(self, element: marko.inline.Emphasis) -> None:
        with self.tagged("italic"):
            self.render_children(element)

    def render_strong_emphasis(self, element: marko.inline.StrongEmphasis) -> None:
        with self.tagged("bold"):
            self.render_children(element)

    def render_strikethrough(self, element: Strikethrough) -> None:
        with self.tagged("overstrike"):
            self.render_children(element)

    def download_image(self, url: str) -> Path:
        # TODO: run this in another thread?
        path = Path(tempfile.mkstemp()[1])

        request = urllib.request.Request(url=url, headers={"User-Agent": "Mozilla/6.0"})
        response = urllib.request.urlopen(request)

        path.write_bytes(response.read())
        return path

    def render_image(self, element: marko.inline.Image) -> None:
        source = element.dest

        if source in self.images:
            image = self.images[source]
        else:
            if re.match("^(http|https)://", source):
                path = self.download_image(source)
            elif (self.widget.path.parent / source).is_file():
                path = self.widget.path.parent / source
            else:
                self.render_children(element)
                self.insert("\n")
                return

            try:
                image = tkinter.PhotoImage(file=path)
            except tkinter.TclError:
                # Unsupported file, or smth
                return

            self.images[source] = image

        self.widget.image_create("end", image=image)
        self.insert("\n")

    def get_link(self, url):
        if re.match("^(http|https|ftp)://", url):
            return URL(url)
        elif url.startswith("#"):
            return Anchor(url)
        else:
            return File(url)

    def render_link(self, element: marko.inline.Link) -> None:
        with self.tagged("link"):
            self.links[self.widget.index("end - 1 char")] = self.get_link(element.dest)
            self.render_children(element)

    def render_auto_link(self, element: marko.inline.AutoLink) -> None:
        with self.tagged("link"):
            self.links[self.widget.index("end - 1 char")] = self.get_link(element.dest)
            self.insert(element.dest)

    def render_url(self, element: marko.inline.AutoLink) -> None:
        with self.tagged("link"):
            self.links[self.widget.index("end - 1 char")] = URL(element.dest)
            self.insert(element.dest)

    def render_thematic_break(self, element: marko.block.ThematicBreak) -> None:
        # TODO: how to insert a horizontal separator into the text widget?
        pass

    def render_html_block(self, element: marko.block.HTMLBlock) -> None:
        with self.tagged("nospacing"):
            self.insert(element.body)

    def render_inline_html(self, element: marko.inline.InlineHTML) -> None:
        assert isinstance(element.children, str)
        self.insert(element.children)
