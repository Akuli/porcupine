import teek

from porcupine import actions, get_tab_manager, tabs


# TODO: add something like this to teek.extras, tkinter has
#       tkinter.simpledialog for doing these things
class IntegerDialog:

    def __init__(self, title, text):
        self.window = teek.Window(title)
        self.window.on_delete_window.disconnect(teek.quit)  # FIXME: this work?
        self.window.on_delete_window.connect(self.on_cancel)

        self.var = teek.StringVar()

        teek.Label(self.window, text).grid(row=0, column=0, columnspan=2)
        entry = teek.Entry(self.window, textvariable=self.var)
        entry.grid(row=1, column=0, columnspan=2)
        entry.bind('<Return>', self.on_ok)
        entry.bind('<Escape>', self.on_cancel)

        self.ok_button = teek.Button(self.window, "OK", self.on_ok)
        self.ok_button.grid(row=3, column=0)
        teek.Button(self.window, "Cancel", self.on_cancel).grid(
            row=3, column=1)

        self.window.grid_rows[0].config['weight'] = 1
        self.window.grid_rows[2].config['weight'] = 1
        for column in self.window.grid_columns:
            column.config['weight'] = 1

        self.result = None
        self.var.write_trace.connect(self.on_var_changed)
        self.var.set("")

        entry.focus()

    def on_var_changed(self, var):
        try:
            self.result = int(var.get())
            self.ok_button.config['state'] = 'normal'
        except ValueError:
            self.ok_button.config['state'] = 'disabled'

    def on_ok(self):
        # this state check is needed because <Return> is bound to this, and
        # that binding can run even if the button is disabled
        if self.ok_button.config['state'] == 'normal':
            self.window.destroy()

    def on_cancel(self):
        self.result = None
        self.window.destroy()

    def run(self):
        self.window.wait_window()
        return self.result


def gotoline():
    tab = get_tab_manager().selected_tab

    # simpledialog isn't ttk yet, but it's not a huge problem imo
    lineno = IntegerDialog(
        "Go to Line", "Type a line number and press Enter:").run()
    if lineno is not None:    # not cancelled
        # there's no need to do a bounds check because tk handles out-of-bounds
        # text indexes nicely
        # TODO: test this?
        tab.textwidget.marks['insert'] = (
            lineno, tab.textwidget.marks['insert'].column)
        tab.textwidget.see(tab.textwidget.marks['insert'])

    tab.on_focus()


def setup():
    actions.add_command("Edit/Go to Line", gotoline, '<Control-l>',
                        tabtypes=[tabs.FileTab])
