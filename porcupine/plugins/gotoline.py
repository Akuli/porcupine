from tkinter import simpledialog

from porcupine import tabs


def setup(editor):
    def gotoline():
        lineno = simpledialog.askinteger(
            "Go to Line", "Type a line number and press Enter:")
        if lineno is None:    # cancelled
            return

        tab = editor.tabmanager.current_tab
        column = tab.textwidget.index('insert').split('.')[1]
        location = '%d.%s' % (lineno, column)
        tab.textwidget.mark_set('insert', location)
        tab.textwidget.see(location)
        tab.on_focus()

    editor.add_action(gotoline, 'Edit/Go to Line', 'Ctrl+L', '<Control-l>',
                      tabtypes=[tabs.FileTab])
