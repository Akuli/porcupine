from __future__ import annotations

import time
import tkinter

from porcupine import get_tab_manager, tabs
from porcupine.plugins.linenumbers import LineNumbers

# Dependent on code from linenumbers.py
setup_after = ["linenumbers"]


class AnchorManager:
    def __init__(self, tab_textwidget: tkinter.Text, linenumbers: LineNumbers) -> None:
        self.tab_textwidget = tab_textwidget
        self.linenumbers = linenumbers

        self.anchor_symbol = "¶"

        # tkinter have default marks such as "insert", "current", "tkinter::anchor1"
        self.custom_anchor_prefix = "anchor_"

        linenumbers.bind("<<Updated>>", self.update_linenumbers, add=True)

    def _get_anchors(self) -> list[str]:
        return [
            anchor
            for anchor in self.tab_textwidget.mark_names()
            if anchor.startswith(self.custom_anchor_prefix)
        ]

    def _get_cursor_index(self) -> str:
        return self.tab_textwidget.index("insert linestart")

    def toggle_on_off(self, event: tkinter.Event[tkinter.Misc]) -> None:

        self.prevent_duplicate_anchors()

        cursor_index = self._get_cursor_index()
        for anchor in self._get_anchors():
            if self.tab_textwidget.index(anchor) == cursor_index:
                self.tab_textwidget.mark_unset(anchor)
                self.linenumbers.do_update()
                return
        self.tab_textwidget.mark_set(
            self.custom_anchor_prefix + str(time.time()), "insert linestart"
        )

        self.linenumbers.do_update()

    def jump_to_next(self, event: tkinter.Event[tkinter.Misc]) -> None:
        cursor_row = self._get_cursor_index().split(".")[0]
        anchor_list = self._get_anchors()
        anchor_rows = reversed(
            sorted(
                [
                    int(self.tab_textwidget.index(anchorpoint).split(".")[0])
                    for anchorpoint in anchor_list
                ]
            )
        )

        rows_after_cursor = [n for n in anchor_rows if n > int(cursor_row)]
        if rows_after_cursor:
            next_anchor_row = min(rows_after_cursor)
        else:
            next_anchor_row = 0

        if not next_anchor_row:
            return
        else:
            self.tab_textwidget.mark_set("insert", f"{str(next_anchor_row)}.0")

        # If cursor is below last row
        if int(self._get_cursor_index().split(".")[0]) > int(
            self.tab_textwidget.index(f"@0,{self.tab_textwidget.winfo_height()}").split(".")[0]
        ):
            self.tab_textwidget.see("insert")

        # TODO: If user jumps to the last anchor and then to next, it should jump to the first one in the file.

    def jump_to_previous(self, event: tkinter.Event[tkinter.Misc]) -> None:
        cursor_row = self._get_cursor_index().split(".")[0]
        anchor_list = self._get_anchors()
        anchor_rows = sorted(
            [
                int(self.tab_textwidget.index(anchorpoint).split(".")[0])
                for anchorpoint in anchor_list
            ]
        )

        next_anchor_row = 0
        for anchor_row in anchor_rows:
            if anchor_row < int(cursor_row):
                next_anchor_row = anchor_row
            else:
                break

        if not next_anchor_row:
            return
        else:
            self.tab_textwidget.mark_set("insert", f"{str(next_anchor_row)}.0")

        # If cursor is above first row
        if int(self._get_cursor_index().split(".")[0]) < int(
            self.tab_textwidget.index("@0,0").split(".")[0]
        ):
            self.tab_textwidget.see("insert")

        # TODO: Current Bugs:
        # 1) Jump to previous will delete code on current row if no more anchors above.

    # def bind_specific(self, event: tkinter.Event[tkinter.Misc], partial ?) -> None:
    #     pass

    # def jump_to_specific(self, event: tkinter.Event[tkinter.Misc], partial ?) -> None:
    #     pass

    def update_linenumbers(self, event: tkinter.Event[tkinter.Misc]) -> None:
        """
        Re-draws the anchor points every time the linenumber instance updates
        (scroll, insertion/deletion of text)
        """
        self.prevent_duplicate_anchors()

        anchor_list = self._get_anchors()

        for anchorpoint in anchor_list:
            row_tag = "line_" + self.tab_textwidget.index(anchorpoint).split(".")[0]
            try:
                [row_id] = self.linenumbers.find_withtag(row_tag)
                row_text = self.linenumbers.itemcget(row_id, "text")  # type: ignore[no-untyped-call]
                self.linenumbers.itemconfigure(row_id, text=row_text + " " + self.anchor_symbol)
            except ValueError:
                pass

    def prevent_duplicate_anchors(self) -> None:
        current_rows = set()
        anchor_list = self._get_anchors()

        for anchorpoint in anchor_list:
            anchor_row = self.tab_textwidget.index(anchorpoint).split(".")[0]
            if anchor_row in current_rows:
                self.tab_textwidget.mark_unset(anchorpoint)
            else:
                self.tab_textwidget.mark_set(anchorpoint, f"{anchorpoint} linestart")
                current_rows.add(anchor_row)


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        [linenumbers] = [
            child for child in tab.left_frame.winfo_children() if isinstance(child, LineNumbers)
        ]
        anchor = AnchorManager(tab.textwidget, linenumbers)
        tab.textwidget.bind("<Control-g>", anchor.toggle_on_off, add=True)
        tab.textwidget.bind("<Control-k>", anchor.jump_to_previous, add=True)
        tab.textwidget.bind("<Control-l>", anchor.jump_to_next, add=True)
        # TODO: When keybindings decided, add to default_keybindings.tcl


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
