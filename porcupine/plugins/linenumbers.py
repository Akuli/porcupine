"""Line numbers on left side of the file being edited."""
from __future__ import annotations

import tkinter.font

from porcupine import get_tab_manager, tabs, textutils, utils


def line_is_elided(textwidget: tkinter.Text, lineno: int) -> bool:
    tags = textwidget.tag_names(f"{lineno}.0")
    elide_values = (textwidget.tag_cget(tag, "elide") for tag in tags)
    # elide values can be empty
    return any(tkinter.getboolean(v or "false") for v in elide_values)  # type: ignore[no-untyped-call]


class LineNumbers(tkinter.Canvas):
    def __init__(self, parent: tkinter.Misc, textwidget_of_tab: tkinter.Text) -> None:
        super().__init__(parent, highlightthickness=0)
        self._update_width()

        self._textwidget = textwidget_of_tab
        textutils.use_pygments_theme(self, self._set_colors)
        utils.add_scroll_command(textwidget_of_tab, "yscrollcommand", self.do_update)

        textwidget_of_tab.bind(
            "<<ContentChanged>>",
            lambda event: textwidget_of_tab.after_idle(self.do_update),
            add=True,
        )
        self.do_update()

        self.bind("<<SettingChanged:font_family>>", self._update_width, add=True)
        self.bind("<<SettingChanged:font_size>>", self._update_width, add=True)

        self._clicked_place: str | None = None
        self.bind("<Button-1>", self._on_click, add=True)
        self.bind("<ButtonRelease-1>", self._on_unclick, add=True)
        self.bind("<Double-Button-1>", self._on_double_click, add=True)
        self.bind("<Button1-Motion>", self._on_drag, add=True)

    def _set_colors(self, fg: str, bg: str) -> None:
        self.config(background=bg)
        self._text_color = fg
        self.itemconfig("all", fill=fg)

    def do_update(self, junk: object = None) -> None:
        self.delete("all")

        first_line = int(self._textwidget.index("@0,0").split(".")[0])
        last_line = int(
            self._textwidget.index(f"@0,{self._textwidget.winfo_height()}").split(".")[0]
        )
        for lineno in range(first_line, last_line + 1):
            # index('@0,y') doesn't work when scrolled a lot to side, but dlineinfo seems to work
            dlineinfo = self._textwidget.dlineinfo(f"{lineno}.0")
            if dlineinfo is None or line_is_elided(self._textwidget, lineno):
                # line not on screen for whatever reason
                continue

            x, y, *junk = dlineinfo
            self.create_text(
                0,
                y,
                text=f" {lineno}",
                anchor="nw",
                font="TkFixedFont",
                fill=self._text_color,
                tags=f"line_{lineno}",
            )

        # Do this in other plugins: linenumbers.bind("<<Updated>>", do_something, add=True)
        self.event_generate("<<Updated>>")

    def _update_width(self, junk: object = None) -> None:
        self.config(width=tkinter.font.Font(name="TkFixedFont", exists=True).measure(" 1234 "))

    def _on_click(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # go to clicked line
        self._textwidget.tag_remove("sel", "1.0", "end")
        self._textwidget.mark_set("insert", f"@0,{event.y}")
        self._clicked_place = self._textwidget.index("insert")

    def _on_unclick(self, event: tkinter.Event[tkinter.Misc]) -> None:
        self._clicked_place = None

    def _on_double_click(self, event: tkinter.Event[tkinter.Misc]) -> None:
        # select the line the cursor is on, including trailing newline
        self._textwidget.tag_remove("sel", "1.0", "end")
        self._textwidget.tag_add("sel", "insert", "insert + 1 line")

    def _on_drag(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if self._clicked_place is None:
            # the user pressed down the mouse button and then moved the
            # mouse over the line numbers
            return

        # select multiple lines
        self._textwidget.mark_set("insert", f"@0,{event.y}")
        start = "insert"
        end = self._clicked_place
        if self._textwidget.compare(start, ">", end):
            start, end = end, start

        self._textwidget.tag_remove("sel", "1.0", "end")
        self._textwidget.tag_add("sel", start, end)


def on_new_filetab(tab: tabs.FileTab) -> None:
    # Use tab.left_frame.winfo_children() and isinstance to access
    # the LineNumbers instance from another plugin
    LineNumbers(tab.left_frame, tab.textwidget).pack(side="left", fill="y")


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
