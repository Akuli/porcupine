"""Display a "Pastebin" menu that allows you to pastebin files easily.

If a part of the file is selected when you click something in the "Pastebin"
menu, then only the selected part of the file is shared.
"""
# TODO: make this work with pythonprompt plugin?
from __future__ import annotations

import logging
import socket
import ssl
import tkinter
import webbrowser
from functools import partial
from http.client import HTTPConnection, HTTPSConnection
from tkinter import messagebox, ttk
from typing import Any, ClassVar, Type, cast
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, Request, build_opener

from pygments.lexer import LexerMeta

from porcupine import get_main_window, menubar, tabs, utils

log = logging.getLogger(__name__)


DPASTE_URL = "https://dpaste.com/api/v2/"
TERMBIN_HOST_AND_PORT = ("termbin.com", 9999)


class Paste:
    name: ClassVar[str]

    def __init__(self) -> None:
        self.canceled = False

    def get_socket(self) -> socket.socket | ssl.SSLSocket | None:
        raise NotImplementedError

    # runs in a new thread
    def run(self, code: str, lexer_class: LexerMeta) -> str:
        raise NotImplementedError

    def cancel(self) -> bool:
        sock = self.get_socket()
        if sock is None:
            log.info("can't cancel yet")
            return False

        log.debug("canceling (shutting down socket)")
        sock.shutdown(socket.SHUT_RDWR)

        log.debug("canceling done")
        self.canceled = True
        return True


class Termbin(Paste):
    name = "termbin.com"

    def __init__(self) -> None:
        super().__init__()
        self._socket: socket.socket | None = None

    def get_socket(self) -> socket.socket | None:
        return self._socket

    def run(self, code: str, lexer_class: LexerMeta) -> str:
        with socket.socket() as self._socket:
            self._socket.connect(TERMBIN_HOST_AND_PORT)
            self._socket.sendall(code.encode("utf-8"))
            url = self._socket.recv(1024)
            # today termbin adds zero bytes to my URL's 0_o it hasn't done sit before
            # i've never seen it add \r but i'm not surprised if it adds it
            return url.rstrip(b"\n\r\0").decode("ascii")


# Hello there, random person reading my code. You are probably wondering why in
# the world I am using urllib instead of requests.
#
# It doesn't seem to be possible to access the underlying socket that requests
# uses without relying on _methods_named_like_this. We need that socket for
# canceling the pastebinning. For example, https://stackoverflow.com/a/32311849
# is useless because it gives the socket after it's connected, and most of the
# pastebinning time is spent connecting the socket (on my system).
class MyHTTPConnection(HTTPConnection):
    def connect(self) -> None:
        # Unlike HTTPConnection.connect, this creates the socket so that it is
        # assinged to self.sock before it's connected.
        self.sock: socket.socket | ssl.SSLSocket = socket.socket()
        self.sock.connect((self.host, self.port))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


# HTTPSConnection does super().connect(), which calls MyHTTPConnection.connect,
# and then it SSL-wraps the socket created by MyHTTPConnection.
class MyHTTPSConnection(HTTPSConnection, MyHTTPConnection):
    def __init__(self, *args: Any, dpaste: DPaste, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._dpaste = dpaste

    # https://github.com/python/mypy/issues/10049
    @property  # type: ignore
    def sock(self) -> socket.socket | ssl.SSLSocket:  # type: ignore
        return self.__sock

    @sock.setter
    def sock(self, new_sock: socket.socket | ssl.SSLSocket) -> None:
        # Canceling with the non-SSL socket fails because making the SSL socket
        # closes the non-SSL socket. So, don't tell the dpaste object about
        # being able to cancel until self.sock is set to SSL socket.
        self.__sock = new_sock
        if isinstance(new_sock, ssl.SSLSocket):
            self._dpaste.connection = self


class DPaste(Paste):
    name = "dpaste.com"

    def __init__(self) -> None:
        super().__init__()
        self.connection: MyHTTPSConnection | None = None

    def get_socket(self) -> ssl.SSLSocket | None:
        if self.connection is None:
            return None
        return cast(ssl.SSLSocket, self.connection.sock)

    def run(self, code: str, lexer_class: LexerMeta) -> str:
        # kwargs of do_open() go to MyHTTPSConnection
        handler = HTTPSHandler()
        handler.https_open = partial(handler.do_open, MyHTTPSConnection, dpaste=self)  # type: ignore

        # docs: https://dpaste.com/api/v2/
        # dpaste.com's syntax highlighting choices correspond with pygments lexers (see tests)
        request = Request(
            DPASTE_URL,
            data=urlencode({"syntax": lexer_class.aliases[0], "content": code}).encode("utf-8"),
        )

        with build_opener(handler).open(request) as response:
            return response.read().decode().strip()


class SuccessDialog(tkinter.Toplevel):
    def __init__(self, url: str):
        super().__init__()
        self._url = url

        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)

        label = ttk.Label(content, text="Here's your link:")
        label.place(relx=0.5, rely=0.15, anchor="center")

        self._entry = ttk.Entry(self, justify="center")
        self._entry.place(relx=0.5, rely=0.4, anchor="center", relwidth=1)
        self._entry.insert(0, url)  # type: ignore[no-untyped-call]
        self._entry.config(state="readonly")  # must be after the insert
        self.bind("<FocusIn>", self._select_all, add=True)
        self._select_all()

        button_info = [
            ("Open in browser", self.open_in_browser),
            ("Copy to clipboard", self.copy_to_clipboard),
            ("Close this dialog", self.destroy),
        ]
        buttonframe = ttk.Frame(self)
        buttonframe.place(relx=0.5, rely=0.8, anchor="center", relwidth=1)
        for text, callback in button_info:
            ttk.Button(buttonframe, text=text, command=callback).pack(side="left", expand=True)

    def _select_all(self, event: tkinter.Event[tkinter.Misc] | None = None) -> None:
        # toplevels annoyingly get notified of child events
        if event is None or event.widget is self:
            self._entry.selection_range(0, "end")  # type: ignore[no-untyped-call]
            self._entry.focus()

    def open_in_browser(self) -> None:
        webbrowser.open(self._url)
        self.destroy()

    def copy_to_clipboard(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self._url)


def make_please_wait_window(paste: Paste) -> tkinter.Toplevel:
    window = tkinter.Toplevel()
    window.transient(get_main_window())
    window.title("Pasting...")
    window.geometry("350x150")
    window.resizable(False, False)
    window.protocol("WM_DELETE_WINDOW", paste.cancel)

    content = ttk.Frame(window)
    content.pack(fill="both", expand=True)

    label = ttk.Label(
        content, font=("", 12, ()), text=f"Pasting to {type(paste).name}, please wait..."
    )
    label.pack(expand=True)

    progressbar = ttk.Progressbar(content, mode="indeterminate")
    progressbar.pack(fill="x", padx=15, pady=15)
    progressbar.start()

    ttk.Button(content, text="Cancel", command=paste.cancel).pack(pady=15)

    get_main_window().tk.call("tk", "busy", "hold", get_main_window())
    return window


def errordialog(title: str, message: str, monospace_text: str | None = None) -> None:
    window = tkinter.Toplevel()
    if get_main_window().winfo_viewable():
        window.transient(get_main_window())

    # there's nothing but this frame in the window because ttk widgets
    # may use a different background color than the window
    big_frame = ttk.Frame(window)
    big_frame.pack(fill="both", expand=True)

    label = ttk.Label(big_frame, text=message)

    if monospace_text is None:
        label.pack(fill="both", expand=True)
        geometry = "250x150"
    else:
        label.pack(anchor="center")
        # there's no ttk.Text 0_o this looks very different from
        # everything else and it sucks :(
        text = tkinter.Text(big_frame, width=1, height=1)
        text.pack(fill="both", expand=True)
        text.insert("1.0", monospace_text)
        text.config(state="disabled")
        geometry = "400x300"

    button = ttk.Button(big_frame, text="OK", command=window.destroy)
    button.pack(pady=10)
    button.focus()
    button.bind("<Return>", (lambda event: button.invoke()), add=True)  # type: ignore[no-untyped-call]

    window.title(title)
    window.geometry(geometry)
    window.wait_window()


def pasting_done_callback(
    paste: Paste, please_wait_window: tkinter.Toplevel, success: bool, result: str
) -> None:
    get_main_window().tk.call("tk", "busy", "forget", get_main_window())
    please_wait_window.destroy()

    if success:
        if result.startswith(("http://", "https://")):
            log.info("pasting succeeded")
            dialog = SuccessDialog(url=result)
            dialog.title("Pasting Succeeded")
            dialog.geometry("450x150")
            dialog.transient(get_main_window())
            dialog.wait_window()
        else:
            log.error(f"pastebin {paste.name!r} returned invalid url: {result!r}")
            messagebox.showerror(
                "Pasting failed", f"Instead of a valid URL, {type(paste).name} returned {result!r}."
            )
    elif paste.canceled:
        # Log error with less dramatic log level and don't show in GUI
        log.debug("Pasting failed and was cancelled. Here is the error.", exc_info=True)
    else:
        # result is the traceback as a string
        log.error(f"pasting failed\n{result}")
        errordialog(
            "Pasting Failed",
            (
                "Check your internet connection and try again.\n\n"
                + "Here's the full error message:"
            ),
            monospace_text=result,
        )


def start_pasting(paste_class: Type[Paste], tab: tabs.FileTab) -> None:
    lexer_class = tab.settings.get("pygments_lexer", LexerMeta)
    try:
        code = tab.textwidget.get("sel.first", "sel.last")
    except tkinter.TclError:
        # nothing is selected, pastebin everything
        code = tab.textwidget.get("1.0", "end - 1 char")

    paste = paste_class()
    plz_wait = make_please_wait_window(paste)
    utils.run_in_thread(
        partial(paste.run, code, lexer_class), partial(pasting_done_callback, paste, plz_wait)
    )


def setup() -> None:
    for klass in [DPaste, Termbin]:
        assert "/" not in klass.name
        menubar.add_filetab_command(f"Pastebin/{klass.name}", partial(start_pasting, klass))
