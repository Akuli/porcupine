import functools
import getpass    # for getting the user name
import logging
import tkinter
from tkinter import messagebox, ttk

from porcupine import utils

from . import backend

log = logging.getLogger(__name__)


# TODO: this is ok for connecting the first time, but the defaults should go
#       to porcupine.settings or something
#       freenode and current username suck
class ConnectDialogContent(ttk.Frame):

    def __init__(self, master, on_cancel_or_after_connect, **kwargs):
        super().__init__(master, **kwargs)
        self._on_cancel_or_after_connect = on_cancel_or_after_connect

        self.result = None   # will be set to the IrcCore, see connect()

        self._rownumber = 0
        self.grid_columnconfigure(0, minsize=60)
        self.grid_columnconfigure(1, weight=1)

        self._server_entry = ttk.Entry(self)
        self._server_entry.insert(0, 'chat.freenode.net')
        self._add_row("Server:", self._server_entry)

        self._channel_entry = ttk.Entry(self)
        self._add_row("Channel:", self._channel_entry)

        self._nickvar = tkinter.StringVar()
        self._nickvar.set(getpass.getuser())
        self._nickvar.trace('w', self._on_nick_changed)
        self._add_row("Nickname:", ttk.Entry(self, textvariable=self._nickvar))

        button = ttk.Button(self, text="More options...")
        button['command'] = functools.partial(self._show_more, button)
        button.grid(row=self._rownumber, column=0, columnspan=4,
                    sticky='w', padx=5, pady=5)
        # leave self._rownumber untouched

        # _show_more() actually shows these
        self._username_entry = ttk.Entry(self)
        self._realname_entry = ttk.Entry(self)
        self._on_nick_changed()
        self._port_entry = ttk.Entry(self, width=8)
        self._port_entry.insert(0, '6667')

        # big row makes sure that this is always below everything
        self._statuslabel = ttk.Label(self)
        self._statuslabel.grid(row=30, column=0, columnspan=4,
                               pady=5, sticky='swe')
        self._statuslabel.bind(
            '<Configure>',
            lambda event: self._statuslabel.config(wraplength=event.width))
        self.grid_rowconfigure(30, weight=1)

        self._bottomframe = ttk.Frame(self)
        self._bottomframe.grid(row=31, column=0, columnspan=4,
                               padx=5, pady=5, sticky='we')

        ttk.Button(self._bottomframe, text="Cancel",
                   command=self.cancel).pack(side='right')
        ttk.Button(self._bottomframe, text="Connect!",
                   command=self.connect).pack(side='right')

    def _setup_entry_bindings(self, entry):
        entry.bind('<Return>', self.connect, add=True)
        entry.bind('<Escape>', self.cancel, add=True)

    def _add_row(self, label, widget):
        ttk.Label(self, text=label).grid(row=self._rownumber, column=0,
                                         sticky='w')
        widget.grid(row=self._rownumber, column=1, columnspan=3, sticky='we')
        if isinstance(widget, ttk.Entry):
            self._setup_entry_bindings(widget)
        self._rownumber += 1

    def _on_nick_changed(self, *junk):
        self._username_entry.delete(0, 'end')
        self._username_entry.insert(0, self._nickvar.get())
        self._realname_entry.delete(0, 'end')
        self._realname_entry.insert(0, self._nickvar.get())

    # TODO: 2nd alternative for nicknames
    # rest of the code should also handle nickname errors better
    # https://tools.ietf.org/html/rfc1459#section-4.1.2
    def _show_more(self, show_more_button):
        show_more_button.destroy()

        self._server_entry.grid_configure(columnspan=1)
        ttk.Label(self, text="Port:").grid(row=0, column=2)
        self._port_entry.grid(row=0, column=3)
        self._setup_entry_bindings(self._port_entry)

        self._add_row("Username:", self._username_entry)
        self._add_row("Real* name:", self._realname_entry)

        infolabel = ttk.Label(self, text=(
            "* This doesn't need to be your real name.\n"
            "   You can set this to anything you want."))
        infolabel.grid(row=self._rownumber, column=0, columnspan=4, sticky='w',
                       padx=5, pady=5)
        self._rownumber += 1

        self.event_generate('<<MoreOptions>>')

    def cancel(self, junk_event=None):
        self._on_cancel_or_after_connect()

    def connect(self, junk_event=None):
        """Create an IrcCore.

        On success, this sets self.result to the connected core and
        calls on_cancel_or_after_connect(), and on error this shows an
        error message instead.
        """
        # TODO: is realname allowed to be empty?
        for what, value in [("server", self._server_entry.get()),
                            ("nickname", self._nickvar.get()),
                            ("username", self._username_entry.get()),
                            ("realname", self._realname_entry.get()),
                            ("channel", self._channel_entry.get())]:
            if not value:
                # all of these are correct: "a server", "a nickname",
                # "a username", "a channel"
                # so we can use 'a %s'
                messagebox.showerror(
                    "Missing %s" % what,
                    "Please specify a %s and try again." % what)
                return

        # this sucks, see rfc2812
        if not self._channel_entry.get().startswith('#'):
            messagebox.showerror(
                "Invalid channel name",
                "Channel names must start with a # character.")
            return

        try:
            port = int(self._port_entry.get())
            if port <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid port number",
                "'%s' is not a positive integer." % self._port_entry.get())
            return

        disabled = self.winfo_children() + self._bottomframe.winfo_children()
        disabled.remove(self._bottomframe)
        disabled.remove(self._statuslabel)
        for widget in disabled:
            widget['state'] = 'disabled'

        progressbar = ttk.Progressbar(self._bottomframe, mode='indeterminate')
        progressbar.pack(side='left', fill='both', expand=True)
        progressbar.start()
        self._statuslabel['text'] = "Connecting..."

        # creating an IrcCore creates a socket, but that shouldn't block
        # toooo much
        core = backend.IrcCore(
            self._server_entry.get(), port, self._nickvar.get(),
            self._username_entry.get(), self._realname_entry.get(),
            autojoin=[self._channel_entry.get()])

        # this will be ran from tk's event loop
        def on_connect_done(succeeded, result):
            for widget in disabled:
                widget['state'] = 'normal'
            progressbar.destroy()

            if succeeded:
                self.result = core
                self._on_cancel_or_after_connect()
            else:
                # result is a traceback string
                log.error("connecting to %s:%d failed\n%s",
                          core.host, core.port, result)

                last_line = result.splitlines()[-1]
                self._statuslabel['text'] = (
                    "Connecting to %s failed!\n%s" % (core.host, last_line))

        utils.run_in_thread(core.connect, on_connect_done)


def run(transient_to):
    """Returns a connected IrcCore, or None if the user cancelled."""
    dialog = tkinter.Toplevel()

    content = ConnectDialogContent(dialog, dialog.destroy)
    content.pack(fill='both', expand=True)

    dialog.title("Connect to IRC")
    dialog.resizable(False, False)
    dialog.geometry('350x200')
    content.bind('<<MoreOptions>>', (lambda event: dialog.geometry('350x250')))
    dialog.transient(transient_to)

    dialog.wait_window()
    return content.result
