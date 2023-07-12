"""
Sort the selected lines alphabetically. Available in menubar → Edit → Sort Lines.

To sort lines that are indented or surrounded by blank lines, you can simply
place the cursor somewhere in the middle without selecting anything and run the
sort. In other words, if there is nothing selected, this plugin will select
lines above and below the cursor location, excluding blank lines or any lines
with less indentation.
"""

from __future__ import annotations

import tkinter

from porcupine import menubar, tabs, textutils


def can_extend_default_selection(text: tkinter.Text, required_prefix: str, new_lineno: int) -> bool:
    line = text.get(f"{new_lineno}.0", f"{new_lineno + 1}.0")
    return bool(line.strip()) and line.startswith(required_prefix)


def find_chunk_around_cursor(text: tkinter.Text) -> tuple[int, int]:
    cursor_lineno = int(text.index("insert").split(".")[0])
    cursor_line = text.get("insert linestart", "insert lineend")
    cursor_line_indentation = cursor_line[: (len(cursor_line) - len(cursor_line.lstrip()))]

    start = cursor_lineno
    while can_extend_default_selection(text, cursor_line_indentation, start - 1):
        start -= 1

    end = cursor_lineno
    while can_extend_default_selection(text, cursor_line_indentation, end + 1):
        end += 1

    return (start, end)


def sort(tab: tabs.FileTab) -> None:
    try:
        first_line = int(tab.textwidget.index("sel.first").split(".")[0])
        # If last selected character is newline, ignore it
        last_line = int(tab.textwidget.index("sel.last - 1 char").split(".")[0])
    except tkinter.TclError:
        first_line, last_line = find_chunk_around_cursor(tab.textwidget)

    old_lines = tab.textwidget.get(f"{first_line}.0", f"{last_line}.0 lineend").splitlines()
    new_lines = sorted(old_lines)

    with textutils.change_batch(tab.textwidget):
        for lineno, (old, new) in enumerate(zip(old_lines, new_lines), start=first_line):
            if old != new:
                tab.textwidget.replace(f"{lineno}.0", f"{lineno}.0 lineend", new)

    tab.textwidget.tag_remove("sel", "1.0", "end")
    tab.textwidget.tag_add("sel", f"{first_line}.0", f"{last_line + 1}.0")


def setup() -> None:
    menubar.add_filetab_command("Edit/Sort Lines", sort)
