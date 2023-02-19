"""
Allow for easy navigation in your files by toggling on/off anchorpoints,
and jumping back and forth between them.
"""
from __future__ import annotations

import time
import tkinter
from weakref import WeakKeyDictionary

from porcupine import get_tab_manager, menubar, settings, tabs
from porcupine.plugins.linenumbers import LineNumbers
from porcupine.settings import global_settings

# Dependent on code from linenumbers.py
setup_after = ["linenumbers"]


class AnchorManager:
    def __init__(self, tab_textwidget: tkinter.Text, linenumbers: LineNumbers) -> None:
        self.tab_textwidget = tab_textwidget
        self.linenumbers = linenumbers

        # tkinter have default marks such as "insert", "current", "tk::anchor1"
        self.custom_anchor_prefix = "anchor_"

        linenumbers.bind("<<Updated>>", self.on_linenumbers_updated, add=True)

    def _get_anchor_marks(self) -> list[str]:
        return [
            anchor
            for anchor in self.tab_textwidget.mark_names()
            if anchor.startswith(self.custom_anchor_prefix)
        ]

    def _get_line_number(self, index: str) -> int:
        return int(self.tab_textwidget.index(index).split(".")[0])

    def clean_duplicates_and_get_anchor_dict(self) -> dict[int, str]:
        anchors = {}

        for mark in self._get_anchor_marks():
            anchor_row = self._get_line_number(mark)
            if anchor_row in anchors:
                self.tab_textwidget.mark_unset(mark)
            else:
                self.tab_textwidget.mark_set(mark, f"{mark} linestart")
                anchors[anchor_row] = mark

        return anchors

    def add_anchor(self, lineno: int) -> str:
        mark = self.custom_anchor_prefix + str(time.time())
        self.tab_textwidget.mark_set(mark, f"{lineno}.0")
        return mark

    # See underlines.py and langserver.py
    def add_from_underlines(self) -> None:
        anchors = self.clean_duplicates_and_get_anchor_dict()
        for start in self.tab_textwidget.tag_ranges("underline:diagnostics")[::2]:
            lineno = self._get_line_number(str(start))
            if lineno not in anchors:
                anchors[lineno] = self.add_anchor(lineno)
        self.linenumbers.do_update()

    def toggle(self) -> None:
        anchors = self.clean_duplicates_and_get_anchor_dict()
        cursor_lineno = self._get_line_number("insert")
        if cursor_lineno in anchors:
            self.tab_textwidget.mark_unset(anchors[cursor_lineno])
        else:
            self.add_anchor(cursor_lineno)
        self.linenumbers.do_update()

    def jump_to_next(self) -> str:
        cursor_row = self._get_line_number("insert")
        anchor_rows = self.clean_duplicates_and_get_anchor_dict().keys()

        rows_after_cursor = [n for n in anchor_rows if n > cursor_row]
        if rows_after_cursor:
            next_anchor_row = min(rows_after_cursor)
            self.tab_textwidget.mark_set("insert", f"{next_anchor_row}.0")
            self.tab_textwidget.see("insert")
        elif len(anchor_rows) >= 2 and global_settings.get("anchors_cycle", bool):
            next_anchor_row = min(anchor_rows)
            self.tab_textwidget.mark_set("insert", f"{next_anchor_row}.0")
            self.tab_textwidget.see("insert")

        return "break"

    def jump_to_previous(self) -> str:
        cursor_row = self._get_line_number("insert")
        anchor_rows = self.clean_duplicates_and_get_anchor_dict().keys()

        rows_before_cursor = [n for n in anchor_rows if n < cursor_row]
        if rows_before_cursor:
            previous_anchor_row = max(rows_before_cursor)
            self.tab_textwidget.mark_set("insert", f"{previous_anchor_row}.0")
            self.tab_textwidget.see("insert")
        elif len(anchor_rows) >= 2 and global_settings.get("anchors_cycle", bool):
            previous_anchor_row = max(anchor_rows)
            self.tab_textwidget.mark_set("insert", f"{previous_anchor_row}.0")
            self.tab_textwidget.see("insert")

        return "break"

    def on_linenumbers_updated(self, junk_event: object = None) -> None:
        """
        Re-draws the anchor points every time the linenumber instance updates
        (scroll, insertion/deletion of text)
        """
        anchors = self.clean_duplicates_and_get_anchor_dict()
        for lineno in anchors.keys():
            try:
                [row_id] = self.linenumbers.find_withtag(f"line_{lineno}")
            except ValueError:  # if line with anchor isn't visible.
                pass
            else:
                row_text = self.linenumbers.itemcget(row_id, "text")
                self.linenumbers.itemconfigure(row_id, text=row_text + "¶")

    def clear(self) -> None:
        for mark in self._get_anchor_marks():
            self.tab_textwidget.mark_unset(mark)
        self.linenumbers.do_update()


managers: WeakKeyDictionary[tabs.FileTab, AnchorManager] = WeakKeyDictionary()


def on_new_filetab(tab: tabs.FileTab) -> None:
    managers[tab] = AnchorManager(tab.textwidget, tab.left_frame.nametowidget("linenumbers"))


def setup() -> None:
    global_settings.add_option("anchors_cycle", False)
    settings.add_checkbutton(
        "anchors_cycle", text="Jumping to previous/next anchor cycles to end/start of file"
    )
    get_tab_manager().add_filetab_callback(on_new_filetab)

    menubar.add_filetab_command(
        "Edit/Anchors/Add or remove on this line", lambda tab: managers[tab].toggle()
    )
    menubar.add_filetab_command(
        "Edit/Anchors/Jump to previous", lambda tab: managers[tab].jump_to_previous()
    )
    menubar.add_filetab_command(
        "Edit/Anchors/Jump to next", lambda tab: managers[tab].jump_to_next()
    )
    menubar.add_filetab_command("Edit/Anchors/Clear", lambda tab: managers[tab].clear())
    menubar.add_filetab_command(
        "Edit/Anchors/Add to error//warning lines", lambda tab: managers[tab].add_from_underlines()
    )

    # Disable accessing submenu, makes gui look nicer
    menubar.set_enabled_based_on_tab("Edit/Anchors", lambda tab: isinstance(tab, tabs.FileTab))
