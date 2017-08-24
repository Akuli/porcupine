from tkinter import simpledialog

import porcupine
from porcupine import tabs


def gotoline():
    tab = porcupine.get_tab_manager().current_tab

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
    porcupine.add_action(gotoline, 'Edit/Go to Line',
                         ('Ctrl+L', '<Control-l>'), tabtypes=[tabs.FileTab])
