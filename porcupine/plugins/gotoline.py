"""Jump to a given line number easily."""

from tkinter import simpledialog

from porcupine import get_tab_manager, menubar, tabs


def gotoline(tab: tabs.FileTab) -> None:
    # simpledialog isn't ttk yet, but it's not a huge problem imo
    lineno = simpledialog.askinteger(
        "Go to Line", "Type a line number and press Enter:", parent=tab.winfo_toplevel()
    )
    if lineno is not None:  # not cancelled
        # there's no need to do a bounds check because tk ignores out-of-bounds
        # text indexes
        column = tab.textwidget.index("insert").split(".")[1]
        tab.textwidget.mark_set("insert", f"{lineno}.{column}")
        tab.textwidget.see("insert")

    tab.textwidget.focus()


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.bind("<<FiletabCommand:Edit/Go to Line>>", (lambda event: gotoline(tab)), add=True)


def setup() -> None:
    menubar.add_filetab_command("Edit/Go to Line")
    get_tab_manager().add_filetab_callback(on_new_filetab)
