from tkinter import simpledialog

import porcupine
from porcupine import tabs


def gotoline():
    lineno = simpledialog.askinteger(
        "Go to Line", "Type a line number and press Enter:")
    if lineno is None:    # cancelled
        return

    tab = porcupine.get_tab_manager().current_tab
    column = tab.textwidget.index('insert').split('.')[1]
    tab.textwidget.mark_set('insert', '%d.%s' % (lineno, column))
    tab.textwidget.see('insert')
    tab.on_focus()


def setup():
    porcupine.add_action(gotoline, 'Edit/Go to Line',
                         ('Ctrl+L', '<Control-l>'), tabtypes=[tabs.FileTab])
