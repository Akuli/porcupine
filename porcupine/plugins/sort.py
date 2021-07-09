"""
Sort the selected lines alphabetically, or if there's no selection, sort between surrounding blank lines.

Available in Edit/Sort Lines.
"""

import tkinter

from porcupine import menubar, tabs, textutils


def sort(tab: tabs.FileTab) -> None:
    try:
        first_line = int(tab.textwidget.index("sel.first").split(".")[0])
        # If last selected character is newline, ignore it
        last_line = int(tab.textwidget.index("sel.last - 1 char").split(".")[0])
    except tkinter.TclError:
        # Nothing selected, find blank line separated part
        first_line = last_line = int(tab.textwidget.index("insert").split(".")[0])
        while tab.textwidget.get(f"{first_line - 1}.0", f"{first_line}.0").strip():
            first_line -= 1
        while tab.textwidget.get(f"{last_line + 1}.0", f"{last_line + 2}.0").strip():
            last_line += 1

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
