"""Fold parts of code with Edit/Fold."""
import tkinter
from typing import Optional

from porcupine import menubar, tabs, utils
from porcupine.plugins.linenumbers import LineNumbers


def get_indent(tab: tabs.FileTab, lineno: int) -> Optional[int]:
    line = tab.textwidget.get(f"{lineno}.0", f"{lineno}.0 lineend")
    line = line.expandtabs(tab.settings.get("indent_size", int))
    without_indent = line.lstrip()
    if not without_indent:
        return None
    return len(line) - len(without_indent)


def find_indented_block(tab: tabs.FileTab, lineno: int) -> Optional[int]:
    original_indent = get_indent(tab, lineno)
    if original_indent is None:
        return None

    last_lineno = lineno
    max_lineno = int(tab.textwidget.index("end - 1 line").split(".")[0])
    while last_lineno < max_lineno:
        next_indent = get_indent(tab, last_lineno + 1)
        if next_indent is not None and next_indent <= original_indent:
            break
        last_lineno += 1

    # Don't hide trailing blank lines
    while (
        last_lineno > lineno
        and not tab.textwidget.get(f"{last_lineno}.0", f"{last_lineno}.0 lineend").strip()
    ):
        last_lineno -= 1

    if last_lineno == lineno:
        return None
    return last_lineno


def fold(tab: tabs.FileTab) -> None:
    lineno = int(tab.textwidget.index("insert").split(".")[0])
    end = find_indented_block(tab, lineno)
    if end is None:
        return

    old_folds = [
        tag for tag in tab.textwidget.tag_names(f"{lineno + 1}.0") if tag.startswith("fold_")
    ]
    if old_folds:
        [tag] = old_folds
        assert tag.startswith("fold_")
        window_name = tag[len("fold_") :]
        tab.textwidget.delete(window_name)
        return

    # Make it possible to get dots widget from tag name (needed above)
    dots = tkinter.Label(
        tab.textwidget,
        text="    ⬤ ⬤ ⬤    ",
        font=("", 3, ""),
        cursor="hand2",
        fg=tab.textwidget["fg"],
        bg=utils.mix_colors(tab.textwidget["fg"], tab.textwidget["bg"], 0.2),
    )
    tag = f"fold_{dots}"

    tab.textwidget.tag_config(tag, elide=True)
    tab.textwidget.tag_add(tag, f"{lineno + 1}.0", f"{end + 1}.0")

    dots.bind("<Destroy>", lambda event: tab.textwidget.tag_delete(tag), add=True)
    dots.bind("<Button-1>", lambda event: tab.textwidget.delete(dots), add=True)
    tab.textwidget.window_create(f"{lineno}.0 lineend", window=dots)  # type: ignore[no-untyped-call]

    for child in tab.left_frame.winfo_children():
        if isinstance(child, LineNumbers):
            child.do_update()


def setup() -> None:
    menubar.add_filetab_command("Edit/Fold", fold)
