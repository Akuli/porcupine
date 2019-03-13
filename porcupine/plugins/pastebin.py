# remember to update this file if the pythonprompt plugin will work some day
# FIXME: this is way too python-specific :(

import contextlib
import functools
import logging
import socket
import threading
import traceback
import webbrowser

import teek as tk
import requests

from porcupine import actions, get_main_window, get_tab_manager, tabs, utils
from porcupine import __version__ as _porcupine_version


if tk.TK_VERSION >= (8, 6):
    @contextlib.contextmanager
    def busy(widget):
        with widget.busy():
            yield

else:    # pragma: no cover
    # TODO: gray out something?
    @contextlib.contextmanager
    def busy(widget):
        yield


log = logging.getLogger(__name__)
pastebins = {}


def pastebin(name):
    def inner(function):
        pastebins[name] = function
        return function

    return inner


@pastebin("termbin.com")
def paste_to_termbin(code, path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('termbin.com', 9999))
        sock.send(code.encode('utf-8'))
        url = sock.recv(1024)
        if url.startswith(b'Use netcat'):   # pragma: no cover
            raise RuntimeError("sending to termbin failed (got %r)" % url)

        # today termbin adds zero bytes to my URL's 0_o it hasn't done
        # it before
        # i've never seen it add \r but i'm not surprised if it adds it
        return url.rstrip(b'\n\r\0').decode('ascii')


session = requests.Session()
session.headers['User-Agent'] = "Porcupine/%s" % _porcupine_version


@pastebin("dpaste.com")
def paste_to_dpaste_com(code, path):
    # dpaste doesn't have an https api at the time of writing this
    response = session.post('http://dpaste.com/api/v2/', data={
        'content': code,
        'syntax': 'python3',
    })
    response.raise_for_status()
    return response.text.strip()


@pastebin("dpaste.de")
def paste_to_dpaste_de(code, path):
    # docs: http://dpaste.readthedocs.io/en/latest/api.html
    # the docs tell to post to http://dpaste.de/api/ but they use
    # https://... in the examples 0_o only the https version works
    response = session.post('https://dpaste.de/api/', data={
        'content': code,
        # lexer defaults to 'python'
        'format': 'url',
    })
    response.raise_for_status()
    return response.text.strip()


@pastebin("Ghostbin")
def paste_to_ghostbin(code, path):
    # docs: https://ghostbin.com/paste/p3qcy
    response = session.post(
        'https://ghostbin.com/paste/new',
        data={'text': code},
        params={
            'expire': '30d',
            'lang': 'python3',
        },
    )
    response.raise_for_status()
    return response.url


@pastebin("Paste ofCode")
def paste_to_paste_ofcode(code, path):
    # PurpleMyst figured out this stuff a long time ago... it's not documented
    # anywhere, but it has worked for i think over a year now
    response = session.post('http://paste.ofcode.org/', data={
        'code': code,
        'language': 'python3',
        'notabot': 'most_likely',   # lol
    })
    response.raise_for_status()
    return response.url


class SuccessDialog(tk.Window):

    @tk.make_thread_safe
    def __init__(self, url, **kwargs):
        super().__init__("Pasting Succeeded", **kwargs)
        self.url = url

        label = tk.Label(self, text="Here's your link:")
        label.place(relx=0.5, rely=0.15, anchor='center')

        breaky_select_all = functools.partial(self._select_all, breaking=True)
        entry = self._entry = tk.Entry(self, justify='center')
        entry.place(relx=0.5, rely=0.4, anchor='center', relwidth=1)
        entry.text = url
        entry.config['state'] = 'readonly'     # must be after the insert
        entry.bind('<Control-a>', breaky_select_all)
        entry.bind('<FocusIn>', self._select_all)
        self._select_all()

        button_info = [
            ("Open in browser", self.open_in_browser),
            ("Copy to clipboard", self.copy_to_clipboard),
            ("Close this dialog", self.destroy),
        ]
        buttonframe = tk.Frame(self)
        buttonframe.place(relx=0.5, rely=0.8, anchor='center', relwidth=1)
        for text, callback in button_info:
            button = tk.Button(buttonframe, text=text, command=callback)
            button.pack(side='left', expand=True)

        self.geometry(450, 150)
        self.transient = get_main_window()

        self.on_delete_window.disconnect(tk.quit)
        self.on_delete_window.connect(self.destroy)

    def _select_all(self, breaking=False):
        # TODO: add 'selection range' to pythotk
        tk.tcl_call(None, self._entry, 'selection', 'range', 0, 'end')
        return ('break' if breaking else None)

    def open_in_browser(self):
        webbrowser.open(self.url)
        self.destroy()

    def copy_to_clipboard(self):
        # TODO: add clipboard support to pythotk
        tk.tcl_call(None, 'clipboard', 'clear')
        tk.tcl_call(None, 'clipboard', 'append', '--', self.url)


class Paste:

    def __init__(self, pastebin_name, code, path):
        self.pastebin_name = pastebin_name
        self.content = code
        self.path = path

        window = self.please_wait_window = tk.Window("Pasting...")
        window.transient = get_main_window()
        window.geometry(350, 150)
        # TODO: add 'wm resizable' to pythotk
        tk.tcl_call(None, 'wm', 'resizable', window.toplevel, False, False)

        # make the close button do nothing, there's no good way to cancel this
        # forcefully :(
        window.on_delete_window.disconnect(tk.quit)

        content = tk.Frame(window)
        content.pack(fill='both', expand=True)

        label = tk.Label(
            content, font=('', 12, ''),
            text=("Pasting to %s, please wait..." % self.pastebin_name))
        label.pack(expand=True)

        progressbar = tk.Progressbar(content, mode='indeterminate')
        progressbar.pack(fill='x', padx=15, pady=15)
        progressbar.start()

    def run(self):
        with busy(self.please_wait_window):
            log.debug("starting to paste to %s", self.pastebin_name)
            try:
                url = pastebins[self.pastebin_name](self.content, self.path)
                assert url is not None
            except Exception:
                log.error("pasting failed", exc_info=True)
                utils.errordialog(
                    "Pasting Failed",
                    ("Check your internet connection and try again.\n\n" +
                     "Here's the full error message:"),
                    monospace_text=traceback.format_exc())
                url = None

        self.please_wait_window.destroy()
        if url is not None:
            SuccessDialog(url).wait_window()


def start_pasting(pastebin_name):
    tab = get_tab_manager().selected_tab
    # only pastebin the selected code, if some code is selected
    try:
        # TODO: add support to sel.first and sel.last to pythotk
        [(start, end)] = tab.textwidget.get_tag('sel').ranges()
    except ValueError:
        start = tab.textwidget.start
        end = tab.textwidget.end

    paste = Paste(pastebin_name, tab.textwidget.get(start, end), tab.path)
    threading.Thread(target=paste.run).start()


def setup():
    for name in sorted(pastebins, key=str.casefold):
        assert '/' not in name
        callback = functools.partial(start_pasting, name)
        actions.add_command("Share/" + name, callback, tabtypes=[tabs.FileTab])
