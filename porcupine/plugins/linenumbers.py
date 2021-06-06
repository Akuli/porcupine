"""Line numbers on left side of the file being edited."""
from __future__ import annotations

import tkinter.font
from typing import Optional

from porcupine import get_tab_manager, tabs, textwidget, utils


def line_is_elided(textwidget: tkinter.Text, lineno: int) -> bool:
    tags = textwidget.tag_names(f"{lineno}.0")
    elide_values = (textwidget.tag_cget(tag, "elide") for tag in tags)
    # elide values can be empty
    return any(tkinter.getboolean(v or "false") for v in elide_values)  # type: ignore[no-untyped-call]


class LineNumbers:
    def __init__(self, parent: tkinter.Misc, textwidget_of_tab: tkinter.Text) -> None:
        self.textwidget = textwidget_of_tab
        self.canvas = tkinter.Canvas(parent, width=40, highlightthickness=0)
        textwidget.use_pygments_theme(self.canvas, self._set_colors)
        utils.add_scroll_command(textwidget_of_tab, "yscrollcommand", self._do_update)

        textwidget_of_tab.bind(
            "<<ContentChanged>>",
            lambda event: textwidget_of_tab.after_idle(self._do_update),
            add=True,
        )
        textwidget_of_tab.bind(
            "<<UpdateLineNumbers>>", self._do_update, add=True
        )  # TODO: document this?
        self._do_update()

        self.canvas.bind("<<SettingChanged:font_family>>", self._update_canvas_width, add=True)
        self.canvas.bind("<<SettingChanged:font_size>>", self._update_canvas_width, add=True)
        self._update_canvas_width()

        self._clicked_place: Optional[str] = None
        self.canvas.bind("<Button-1>", self._on_click, add=True)
        self.canvas.bind("<ButtonRelease-1>", self._on_unclick, add=True)
        self.canvas.bind("<Double-Button-1>", self._on_double_click, add=True)
        self.canvas.bind("<Button1-Motion>", self._on_drag, add=True)

    def _set_colors(self, fg: str, bg: str) -> None:
        self.canvas.config(background=bg)
        self._text_color = fg
        self.canvas.itemconfig("all", fill=fg)

    def _do_update(self, junk: object = None) -> None:
        self.canvas.delete("all")  # type: ignore[no-untyped-call]

        first_line = int(self.textwidget.index("@0,0").split(".")[0])
        last_line = int(self.textwidget.index(f"@0,{self.textwidget.winfo_height()}").split(".")[0])
        for lineno in range(first_line, last_line + 1):
            # index('@0,y') doesn't work when scrolled a lot to side, but dlineinfo seems to work
            dlineinfo = self.textwidget.dlineinfo(f"{lineno}.0")
            if dlineinfo is None or line_is_elided(self.textwidget, lineno):
                # line not on screen for whatever reason
                continue

            x, y, *junk = dlineinfo
            self.canvas.create_text(  # type: ignore[no-untyped-call]
                0, y, text=f" {lineno}", anchor="nw", font="TkFixedFont", fill=self._text_color
            )

    def _update_canvas_width(self, junk: object = None) -> None:
        self.canvas.config(
            width=tkinter.font.Font(name="TkFixedFont", exists=True).measure(" 1234 ")
        )

    def _on_click(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # go to clicked line
        self.textwidget.tag_remove("sel", "1.0", "end")
        self.textwidget.mark_set("insert", f"@0,{event.y}")
        self._clicked_place = self.textwidget.index("insert")

    def _on_unclick(self, event: tkinter.Event[tkinter.Misc]) -> None:
        self._clicked_place = None

    def _on_double_click(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # select the line the cursor is on, including trailing newline
        self.textwidget.tag_remove("sel", "1.0", "end")
        self.textwidget.tag_add("sel", "insert", "insert + 1 line")

    def _on_drag(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if self._clicked_place is None:
            # the user pressed down the mouse button and then moved the
            # mouse over the line numbers
            return

        # select multiple lines
        self.textwidget.mark_set("insert", f"@0,{event.y}")
        start = "insert"
        end = self._clicked_place
        if self.textwidget.compare(start, ">", end):
            start, end = end, start

        self.textwidget.tag_remove("sel", "1.0", "end")
        self.textwidget.tag_add("sel", start, end)


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        linenumbers = LineNumbers(tab.left_frame, tab.textwidget)
        linenumbers.canvas.pack(side="left", fill="y")


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
