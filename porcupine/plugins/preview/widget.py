import tkinter
from pathlib import Path

import marko

from porcupine.utils import add_scroll_command, mix_colors

from .gfm import GithubFlavoredMarkdown
from .renderer import MarkupPreviewRenderer


class MarkupPreview(tkinter.Text):
    def __init__(self, master: tkinter.Widget, *, editor: tkinter.Text, path: Path) -> None:
        super().__init__(
            master,
            font=("Segoe UI Variable Static Text", -15),
            highlightthickness=0,
            borderwidth=1,
            relief="solid",
            spacing1=10,
            spacing3=6,
            padx=10,
            wrap="word",
            cursor="arrow",
        )
        self.path = path
        self.editor = editor
        self.parser = marko.Markdown(extensions=[GithubFlavoredMarkdown])
        self.renderer = MarkupPreviewRenderer(self)

        add_scroll_command(editor, "yscrollcommand", self._scroll_with_editor)
        editor.bind("<<ContentChanged>>", self.update_preview, add=True)

        self.tag_bind("link", "<Enter>", lambda e: self.config(cursor="hand2"))
        self.tag_bind("link", "<Leave>", lambda e: self.config(cursor="arrow"))
        self.tag_bind("link", "<Button-1>", self.handle_link_open)

        self.bind("<<ThemeChanged>>", self.update_tags)
        self.update_tags()
        self.update_preview()

    def _scroll_with_editor(self) -> None:
        # FIXTHIS

        length = int(self.editor.index("end").split(".")[0])
        first = int(self.editor.index("@0,0 linestart").split(".")[0])
        last = int(self.editor.index("@0,100000 linestart").split(".")[0])
        length -= last - first

        round_ = lambda x: round(x / 0.05) * 0.05

        self.yview_moveto(round_(first / length))

    def update_preview(self, *junk: object) -> None:
        cur = self.editor.index("insert")
        self.config(state="normal")
        self.renderer.clear()
        tree = self.parser.parse(self.editor.get("0.0", "end"))
        self.delete("0.0", "end")
        self.renderer.render(tree)
        self.config(state="disabled")
        self.see(cur)

    def update_tags(self, *_) -> None:
        bg = self.cget("background")
        fg = self.cget("foreground")
        font_family = self.tk.splitlist(self.cget("font"))[0]

        code_options = {"background": mix_colors("#7777aa", bg, 0.3), "font": "TkFixedFont"}
        small_spacing = {"spacing1": 2, "spacing3": 2}
        bold_font = ("-family", font_family, "-weight", "bold")

        self.tag_configure("nospacing", wrap="none", **small_spacing)
        self.tag_configure("highlight", background=mix_colors("#ffff00", bg, 0.5))
        self.tag_configure("link", foreground=mix_colors("#0077ff", fg, 0.6), underline=True)
        self.tag_configure("code_span", lmargincolor=bg, wrap="char", **code_options)
        self.tag_configure("code_block", wrap="none", lmargin1=10, **small_spacing, **code_options)
        self.tag_configure(
            "quote",
            lmargincolor=mix_colors(bg, fg, 0.4),
            foreground=mix_colors(bg, fg, 0.3),
            lmargin1=4,
            lmargin2=4,
            **small_spacing,
        )
        self.tag_configure("bold", font=bold_font)
        self.tag_configure("italic", font=("-family", font_family, "-slant", "italic"))
        self.tag_configure("overstrike", font=("-family", font_family, "-overstrike", "1"))
        self.tag_configure("upper_index", font=("-family", font_family, "-size", -10), offset=5)
        self.tag_configure("footnote", foreground=mix_colors(bg, fg, 0.3))

        for level, size, pad in zip(range(1, 7), range(34, 13, -4), (13, 12, 11, 10, 9, 8)):
            self.tag_configure(
                f"heading_{level}", font=bold_font + ("-size", -size), spacing1=pad, spacing3=2
            )

    def handle_link_open(self, event: tkinter.Event) -> None:
        index = self.index(f"@{event.x},{event.y}")
        ranges = self.tag_ranges("link")
        for start, end in zip(ranges[0::2], ranges[1::2]):
            if self.compare(start, "<=", index) and self.compare(index, "<=", end):
                self.renderer.links[str(start)].open(self)
                break
