"""Display a "Share" menu that allows you to pastebin files easily."""
# remember to update this file if the pythonprompt plugin will work some day

import functools
import logging
import socket
import tkinter
import webbrowser
from tkinter import ttk
from typing import Any, Optional

import requests
from pygments.lexer import LexerMeta  # type: ignore[import]

from porcupine import __version__ as _porcupine_version
from porcupine import get_main_window, get_tab_manager, menubar, tabs, utils

log = logging.getLogger(__name__)


def paste_to_termbin(code: str, lexer_class: LexerMeta) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('termbin.com', 9999))
        sock.send(code.encode('utf-8'))
        url = sock.recv(1024)
        if url.startswith(b'Use netcat'):   # pragma: no cover
            raise RuntimeError(f"sending to termbin failed (got {url!r})")

        # today termbin adds zero bytes to my URL's 0_o it hasn't done
        # it before
        # i've never seen it add \r but i'm not surprised if it adds it
        return url.rstrip(b'\n\r\0').decode('ascii')


session = requests.Session()
session.headers['User-Agent'] = f"Porcupine/{_porcupine_version}"


# dpaste.com's syntax highlighting choices correspond with pygments lexers (see tests)
def paste_to_dpaste_dot_com(code: str, lexer_class: LexerMeta) -> str:
    # docs: https://dpaste.com/api/v2/
    # the docs tell to post to http://dpaste.de/api/ but they use
    # https://... in the examples 0_o only the https version works
    response = session.post('https://dpaste.com/api/v2/', data={
        'syntax': lexer_class.aliases[0],
        'content': code,
    })
    response.raise_for_status()
    return response.text.strip()


pastebins = {"termbin.com": paste_to_termbin, "dpaste.com": paste_to_dpaste_dot_com}


class SuccessDialog(tkinter.Toplevel):

    def __init__(self, url: str, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.url = url

        content = ttk.Frame(self)
        content.pack(fill='both', expand=True)

        label = ttk.Label(content, text="Here's your link:")
        label.place(relx=0.5, rely=0.15, anchor='center')

        breaky_select_all = functools.partial(self._select_all, breaking=True)
        entry = self._entry = ttk.Entry(self, justify='center')
        entry.place(relx=0.5, rely=0.4, anchor='center', relwidth=1)
        entry.insert(0, url)
        entry.config(state='readonly')     # must be after the insert
        entry.bind('<Control-a>', breaky_select_all, add=True)
        entry.bind('<FocusIn>', self._select_all, add=True)
        self._select_all()

        button_info = [
            ("Open in browser", self.open_in_browser),
            ("Copy to clipboard", self.copy_to_clipboard),
            ("Close this dialog", self.destroy),
        ]
        buttonframe = ttk.Frame(self)
        buttonframe.place(relx=0.5, rely=0.8, anchor='center', relwidth=1)
        for text, callback in button_info:
            button = ttk.Button(buttonframe, text=text, command=callback)
            button.pack(side='left', expand=True)

    def _select_all(self, junk: object = None, breaking: bool = False) -> utils.BreakOrNone:
        self._entry.selection_range(0, 'end')
        return ('break' if breaking else None)

    def open_in_browser(self) -> None:
        webbrowser.open(self.url)
        self.destroy()

    def copy_to_clipboard(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.url)


class Paste:

    def __init__(self, pastebin_name: str,
                 code: str, lexer_class: LexerMeta) -> None:
        self.pastebin_name = pastebin_name
        self.content = code
        self.lexer_class = lexer_class
        self.please_wait_window: Optional[tkinter.Toplevel] = None

    def make_please_wait_window(self) -> None:
        window = self.please_wait_window = tkinter.Toplevel()
        window.transient(get_main_window())
        window.title("Pasting...")
        window.geometry('350x150')
        window.resizable(False, False)

        # disable the close button, there's no way to cancel this forcefully :(
        window.protocol('WM_DELETE_WINDOW', (lambda: None))

        content = ttk.Frame(window)
        content.pack(fill='both', expand=True)

        label = ttk.Label(
            content, font=('', 12, ()),
            text=f"Pasting to {self.pastebin_name}, please wait...")
        label.pack(expand=True)

        progressbar = ttk.Progressbar(content, mode='indeterminate')
        progressbar.pack(fill='x', padx=15, pady=15)
        progressbar.start()

    def start(self) -> None:
        log.debug("starting to paste to %s", self.pastebin_name)
        get_main_window().tk.call('tk', 'busy', 'hold', get_main_window())
        self.make_please_wait_window()
        paste_it = functools.partial(
            pastebins[self.pastebin_name], self.content, self.lexer_class)
        utils.run_in_thread(paste_it, self.done_callback)

    def done_callback(self, success: bool, result: str) -> None:
        get_main_window().tk.call('tk', 'busy', 'forget', get_main_window())
        assert self.please_wait_window is not None
        self.please_wait_window.destroy()

        if success:
            log.info("pasting succeeded")
            dialog = SuccessDialog(result)
            dialog.title("Pasting Succeeded")
            dialog.geometry('450x150')
            dialog.transient(get_main_window())
            dialog.wait_window()
        else:
            # result is the traceback as a string
            log.error(f"pasting failed\n{result}")
            utils.errordialog(
                "Pasting Failed",
                ("Check your internet connection and try again.\n\n" +
                 "Here's the full error message:"),
                monospace_text=result)


def start_pasting(pastebin_name: str) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)

    try:
        code = tab.textwidget.get('sel.first', 'sel.last')
    except tkinter.TclError:
        # nothing is selected, pastebin everything
        code = tab.textwidget.get('1.0', 'end - 1 char')

    Paste(pastebin_name, code, tab.settings.get('pygments_lexer', LexerMeta)).start()


def setup() -> None:
    for name in sorted(pastebins, key=str.casefold):
        menubar.get_menu("Share").add_command(label=name, command=functools.partial(start_pasting, name))
        assert '/' not in name
        menubar.set_enabled_based_on_tab(f"Share/{name}", (lambda tab: isinstance(tab, tabs.FileTab)))
