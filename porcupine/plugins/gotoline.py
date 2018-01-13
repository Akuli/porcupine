from tkinter import simpledialog

from porcupine import actions, get_tab_manager, tabs


def gotoline():
    tab = get_tab_manager().select()

    # simpledialog isn't ttk yet, but it's not a huge problem imo
    # TODO: what if lineno is 0 or negative?
    lineno = simpledialog.askinteger(
        "Go to Line", "Type a line number and press Enter:")
    if lineno is not None:    # not cancelled
        column = tab.textwidget.index('insert').split('.')[1]
        tab.textwidget.mark_set('insert', '%d.%s' % (lineno, column))
        tab.textwidget.see('insert')

    tab.on_focus()


def setup():
    actions.add_command("Edit/Go to Line", gotoline, '<Control-l>',
                        tabtypes=[tabs.FileTab])
