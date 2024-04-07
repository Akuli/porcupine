"""Allows you to share snippets of code to others easily.

To use this plugin:

1. Select some code in the editor

2. Right-click the selected code

3. Select "Pastebin selected text to dpaste.com" (or some other site)

4. Wait until you get a link

5. Send the link to someone else
"""
# docstring above needs to have blank lines to show properly in plugin manager
# TODO: make this work with pythonprompt plugin?
from __future__ import annotations

import logging
import socket
import ssl
import textwrap
import tkinter
import webbrowser
from functools import partial
from http.client import HTTPConnection, HTTPSConnection
from tkinter import messagebox, ttk
from typing import Any, ClassVar, cast
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, Request, build_opener

from pygments.lexer import LexerMeta

from porcupine import get_main_window, tabs, utils
from porcupine.plugins import rightclick_menu
from porcupine.settings import global_settings, import_pygments_lexer_class

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

    @property
    def sock(self) -> socket.socket | ssl.SSLSocket:
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

    @staticmethod
    def get_dpaste_name_for_lexer_class(lexer_class: LexerMeta) -> str:
        special_cases = {
            "actionscript3": "as3",
            "actionscript": "as",
            "ambienttalk": "at",
            "antlr-actionscript": "antlr-as",
            "asymptote": "asy",
            "autohotkey": "ahk",
            "batch": "bat",
            "bibtex": "bib",
            "chaiscript": "chai",
            "javascript+cheetah": "js+cheetah",
            "coffeescript": "coffee-script",
            "css+ruby": "css+erb",
            "debcontrol": "control",
            "emacs-lisp": "emacs",
            "gherkin": "cucumber",
            "haxe": "hx",
            "javascript+django": "js+django",
            "javascript+ruby": "js+erb",
            "javascript": "js",
            "javascript+php": "js+php",
            "javascript+smarty": "js+smarty",
            "javascript+lasso": "js+lasso",
            "lighttpd": "lighty",
            "literate-agda": "lagda",
            "literate-cryptol": "lcry",
            "literate-haskell": "lhs",
            "literate-idris": "lidr",
            "livescript": "live-script",
            "javascript+mako": "js+mako",
            "markdown": "md",
            "miniscript": "ms",
            "moonscript": "moon",
            "javascript+myghty": "js+myghty",
            "nimrod": "nim",
            "pwsh-session": "ps1con",
            "rng-compact": "rnc",
            "reasonml": "reason",
            "resourcebundle": "resource",
            "restructuredtext": "rst",
            "trafficscript": "rts",
            "ruby": "rb",
            "debsources": "sourceslist",
            "supercollider": "sc",
            "teratermmacro": "ttl",
            "typescript": "ts",
            "xml+ruby": "xml+erb",
        }
        return special_cases.get(lexer_class.aliases[0], lexer_class.aliases[0])

    def run(self, code: str, lexer_class: LexerMeta) -> str:
        # kwargs of do_open() go to MyHTTPSConnection
        handler = HTTPSHandler()
        handler.https_open = partial(handler.do_open, MyHTTPSConnection, dpaste=self)  # type: ignore

        # docs: https://dpaste.com/api/v2/
        # dpaste.com's syntax highlighting choices correspond with pygments lexers (see tests)
        request = Request(
            DPASTE_URL,
            data=urlencode(
                {"syntax": self.get_dpaste_name_for_lexer_class(lexer_class), "content": code}
            ).encode("utf-8"),
        )

        with build_opener(handler).open(request) as response:
            return response.read().decode().strip()


class SuccessDialog(tkinter.Toplevel):
    def __init__(self, url: str):
        super().__init__()
        self.url = url  # accessed in tests

        content = ttk.Frame(self, padding=10)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)

        label = ttk.Label(content, text="Here's your link:")
        label.grid(row=0, column=0)

        self._entry = ttk.Entry(content, justify="center")
        self._entry.grid(row=1, column=0, sticky="we", pady=(10, 30))
        self._entry.insert(0, url)
        self._entry.config(state="readonly")  # must be after the insert
        self.bind("<FocusIn>", self._select_all, add=True)
        self._select_all()

        button_info = [
            ("Open in browser", self.open_in_browser),
            ("Copy to clipboard", self.copy_to_clipboard),
            ("Close this dialog", self.destroy),
        ]
        buttonframe = ttk.Frame(content)
        buttonframe.grid(row=2, column=0, sticky="we")
        for (text, callback), padx in zip(button_info, [(0, 5), (5, 5), (5, 0)]):
            ttk.Button(buttonframe, text=text, command=callback).pack(
                side="left", expand=True, fill="x", padx=padx
            )

    def _select_all(self, event: tkinter.Event[tkinter.Misc] | None = None) -> None:
        # toplevels annoyingly get notified of child events
        if event is None or event.widget is self:
            self._entry.selection_range(0, "end")
            self._entry.focus()

    def open_in_browser(self) -> None:
        webbrowser.open(self.url)
        self.destroy()

    def copy_to_clipboard(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.url)


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


def pasting_done_callback(
    paste: Paste, please_wait_window: tkinter.Toplevel, success: bool, result: str
) -> None:
    get_main_window().tk.call("tk", "busy", "forget", get_main_window())
    please_wait_window.destroy()

    if success:
        if result.startswith("https://"):
            log.info("pasting succeeded")
            dialog = SuccessDialog(url=result)
            dialog.title("Pasting Succeeded")
            dialog.resizable(False, False)
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
        messagebox.showerror(
            "Pasting failed", "Check your internet connection or try a different pastebin."
        )


def ask_are_you_sure(filename: str | None, paste_class: type[Paste]) -> bool:
    window = tkinter.Toplevel()
    window.title(f"Pastebin {filename}")
    window.transient(get_main_window())

    content = ttk.Frame(window, name="content", padding=10)
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1)

    label1 = ttk.Label(
        content,
        name="label1",
        text=f"Do you want to send the selected text to {paste_class.name}?",
        wraplength=300,
        justify="center",
        font="TkHeadingFont",
    )
    label1.pack(pady=5)

    label2 = ttk.Label(
        content,
        name="label2",
        text="This is a bad idea if your code is not meant to be publicly available.",
        wraplength=300,
        justify="center",
        font="TkTextFont",
    )
    label2.pack(pady=5)

    var = tkinter.BooleanVar(value=True)
    checkbox = ttk.Checkbutton(
        content, text="Show this dialog when I try to pastebin something", variable=var
    )
    checkbox.pack(pady=25)

    result = False

    def yes() -> None:
        nonlocal result
        result = True
        window.destroy()

    def no() -> None:
        window.destroy()

    button_frame = ttk.Frame(content)
    button_frame.pack(fill="x")
    ttk.Button(button_frame, text="Yes", command=yes).pack(
        side="left", expand=True, fill="x", padx=(0, 10)
    )
    ttk.Button(button_frame, text="No", command=no).pack(
        side="left", expand=True, fill="x", padx=(10, 0)
    )

    window.wait_window()
    global_settings.set("ask_to_pastebin", var.get())
    return result


def start_pasting(paste_class: type[Paste], tab: tabs.FileTab) -> None:
    if global_settings.get("ask_to_pastebin", bool):
        filename = "this file" if tab.path is None else tab.path.name
        if not ask_are_you_sure(filename, paste_class):
            return

    code = textwrap.dedent(tab.textwidget.get("sel.first", "sel.last"))
    lexer_class = import_pygments_lexer_class(tab.settings.get("pygments_lexer", str))

    paste = paste_class()
    plz_wait = make_please_wait_window(paste)
    utils.run_in_thread(
        partial(paste.run, code, lexer_class), partial(pasting_done_callback, paste, plz_wait)
    )


def setup() -> None:
    global_settings.add_option("ask_to_pastebin", type=bool, default=True)
    for klass in [DPaste, Termbin]:
        assert "/" not in klass.name
        rightclick_menu.add_rightclick_option(
            f"Pastebin selected text to {klass.name}",
            partial(start_pasting, klass),
            needs_selected_text=True,
        )
