import functools
import getpass    # for getting the user name
import logging
import re
import tkinter
from tkinter import ttk

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

        self._server_entry = self._create_entry()
        self._add_row("Server:", self._server_entry)

        self._channel_entry = self._create_entry()
        self._add_row("Channel:", self._channel_entry)

        self._nick_entry = self._create_entry()
        self._nick_entry.var.trace('w', self._on_nick_changed)
        self._add_row("Nickname:", self._nick_entry)

        button = ttk.Button(self, text="More options...")
        button['command'] = functools.partial(self._show_more, button)
        button.grid(row=self._rownumber, column=0, columnspan=4,
                    sticky='w', padx=5, pady=5)
        # leave self._rownumber untouched

        # _show_more() grids these
        self._username_entry = self._create_entry()
        self._realname_entry = self._create_entry()
        self._port_entry = self._create_entry(width=8)

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
        self._connectbutton = ttk.Button(
            self._bottomframe, text="Connect!", command=self.connect)
        self._connectbutton.pack(side='right')

        # now everything's ready for _validate()
        # all of these call validate()
        self._server_entry.var.set('chat.freenode.net')
        self._nick_entry.var.set(getpass.getuser())
        self._port_entry.var.set('6667')
        self._on_nick_changed()

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

    def _create_entry(self, **kwargs):
        var = kwargs['textvariable'] = tkinter.StringVar()
        var.trace('w', self._validate)
        entry = ttk.Entry(self, **kwargs)
        entry.var = var     # because this is handy
        return entry

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
        # these call self._validate()
        self._username_entry.var.set(self._nick_entry.get())
        self._realname_entry.var.set(self._nick_entry.get())

    def cancel(self, junk_event=None):
        self._on_cancel_or_after_connect()

    def _validate(self, *junk):
        # this will be re-enabled if everything's ok
        self._connectbutton['state'] = 'disabled'

        if not self._server_entry.get():
            self._statuslabel['text'] = "Please specify a server."
            return False
        if not self._nick_entry.get():
            self._statuslabel['text'] = "Please specify a nickname."
            return False
        if not self._username_entry.get():
            self._statuslabel['text'] = "Please specify a username."
            return False
        # TODO: can realname be empty?

        if not re.search('^' + backend.NICK_REGEX + '$',
                         self._nick_entry.get()):
            self._statuslabel['text'] = ("'%s' is not a valid nickname." %
                                         self._nick_entry.get())
            return False

        # if the channel entry is empty, no channels are joined
        channels = self._channel_entry.get().split()
        for channel in channels:
            if not re.fullmatch(backend.CHANNEL_REGEX, channel):
                self._statuslabel['text'] = (
                    "'%s' is not a valid channel name." % channel)

                # see comments of backend.CHANNEL_REGEX
                if not channel.startswith(('&', '#', '+', '!')):
                    # the user probably doesn't know what (s)he's doing
                    self._statuslabel['text'] += (
                        " Usually channel names start with a # character.")
                return False

        try:
            port = int(self._port_entry.get())
            if port <= 0:
                raise ValueError
        except ValueError:
            self._statuslabel['text'] = "The port must be a positive integer."
            return False

        self._statuslabel['text'] = ''
        self._connectbutton['state'] = 'normal'
        return True

    def connect(self, junk_event=None):
        """Create an IrcCore.

        On success, this sets self.result to the connected core and
        calls on_cancel_or_after_connect(), and on error this shows an
        error message instead.
        """
        assert self._validate()
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
            self._server_entry.get(), int(self._port_entry.get()),
            self._nick_entry.get(), self._username_entry.get(),
            self._realname_entry.get(),
            autojoin=self._channel_entry.get().split())

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

    dialog.minsize(350, 200)
    content.bind('<<MoreOptions>>',
                 lambda junk_event: dialog.minsize(350, 250),
                 add=True)

    dialog.title("Connect to IRC")
    dialog.transient(transient_to)
    dialog.wait_window()
    return content.result
