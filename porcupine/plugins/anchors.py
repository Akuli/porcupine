"""
Allow for easy navigation in your files by toggling on/off anchorpoints,
and jumping back and forth between them.
"""
from __future__ import annotations

import time
import tkinter

from porcupine import get_tab_manager, menubar, settings, tabs
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

    def toggle_on_off(self, event: tkinter.Event[tabs.FileTab]) -> None:
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

    def jump_to_next(self, event: tkinter.Event[tabs.FileTab]) -> str:
        cursor_row = self._get_cursor_index().split(".")[0]
        anchor_list = self._get_anchors()
        anchor_rows = [
            int(self.tab_textwidget.index(anchorpoint).split(".")[0]) for anchorpoint in anchor_list
        ]

        rows_after_cursor = [n for n in anchor_rows if n > int(cursor_row)]
        if rows_after_cursor:
            next_anchor_row = min(rows_after_cursor)
            self.tab_textwidget.mark_set("insert", f"{next_anchor_row}.0")
            self.tab_textwidget.see("insert")
        elif len(anchor_list) >= 2 and settings.get("anchors", bool):
            next_anchor_row = min(anchor_rows)
            self.tab_textwidget.mark_set("insert", f"{next_anchor_row}.0")
            self.tab_textwidget.see("insert")

        return "break"

    def jump_to_previous(self, event: tkinter.Event[tabs.FileTab]) -> str:
        cursor_row = self._get_cursor_index().split(".")[0]
        anchor_list = self._get_anchors()
        anchor_rows = [
            int(self.tab_textwidget.index(anchorpoint).split(".")[0]) for anchorpoint in anchor_list
        ]

        rows_before_cursor = [n for n in anchor_rows if n < int(cursor_row)]
        if rows_before_cursor:
            previous_anchor_row = max(rows_before_cursor)
            self.tab_textwidget.mark_set("insert", f"{previous_anchor_row}.0")
            self.tab_textwidget.see("insert")
        elif len(anchor_list) >= 2 and settings.get("anchors", bool):
            previous_anchor_row = max(anchor_rows)
            self.tab_textwidget.mark_set("insert", f"{previous_anchor_row}.0")
            self.tab_textwidget.see("insert")

        return "break"

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
            except ValueError:  # if line with anchor isn't visible.
                pass
            else:
                row_text = self.linenumbers.itemcget(row_id, "text")  # type: ignore[no-untyped-call]
                self.linenumbers.itemconfigure(row_id, text=row_text + " " + self.anchor_symbol)

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


def on_new_filetab(tab: tabs.FileTab) -> None:
    [linenumbers] = [
        child for child in tab.left_frame.winfo_children() if isinstance(child, LineNumbers)
    ]
    manager = AnchorManager(tab.textwidget, linenumbers)
    # fmt: off
    tab.bind("<<FiletabCommand:Edit/Anchors/Add or remove on this line>>", manager.toggle_on_off, add=True)
    tab.bind("<<FiletabCommand:Edit/Anchors/Jump to previous>>", manager.jump_to_previous, add=True)
    tab.bind("<<FiletabCommand:Edit/Anchors/Jump to next>>", manager.jump_to_next, add=True)
    # fmt: on


def setup() -> None:
    settings.add_option("anchors", False)
    settings.add_checkbutton(
        "anchors", text="Jumping to previous/next anchor cycles to end/start of file"
    )
    get_tab_manager().add_filetab_callback(on_new_filetab)

    menubar.add_filetab_command("Edit/Anchors/Add or remove on this line")
    menubar.add_filetab_command("Edit/Anchors/Jump to previous")
    menubar.add_filetab_command("Edit/Anchors/Jump to next")

    # Disable accessing submenu, makes gui look nicer
    menubar.set_enabled_based_on_tab("Edit/Anchors", lambda tab: isinstance(tab, tabs.FileTab))
