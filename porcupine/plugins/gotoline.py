"""Jump to a given line number easily."""

from tkinter import simpledialog

from porcupine import get_tab_manager, menubar, tabs


def gotoline() -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)

    # simpledialog isn't ttk yet, but it's not a huge problem imo
    lineno = simpledialog.askinteger(
        "Go to Line", "Type a line number and press Enter:",
        parent=tab.winfo_toplevel())
    if lineno is not None:    # not cancelled
        # there's no need to do a bounds check because tk ignores out-of-bounds
        # text indexes
        column = tab.textwidget.index('insert').split('.')[1]
        tab.textwidget.mark_set('insert', '%d.%s' % (lineno, column))
        tab.textwidget.see('insert')

    tab.textwidget.focus()


def setup() -> None:
    menubar.get_menu("Edit").add_command(label="Go to Line", command=gotoline)
    menubar.set_enabled_based_on_tab("Edit/Go to Line", (lambda tab: isinstance(tab, tabs.FileTab)))
