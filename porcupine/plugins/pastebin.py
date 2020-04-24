# remember to update this file if the pythonprompt plugin will work some day
# FIXME: this is way too python-specific :(
# FIXME: only two of the 5 pastebins still work, code needs updating
# TODO: cancel button

import functools
import logging
import os
import socket
import tkinter
from tkinter import ttk
import webbrowser

import requests

from porcupine import actions, get_main_window, get_tab_manager, tabs, utils
from porcupine import __version__ as _porcupine_version


if tkinter.TkVersion >= 8.6:    # yes, it's a float in tkinter
    def tk_busy_hold():
        get_main_window().tk.call('tk', 'busy', 'hold', get_main_window())

    def tk_busy_forget():
        get_main_window().tk.call('tk', 'busy', 'forget', get_main_window())

else:    # pragma: no cover
    # TODO: gray out something?
    def tk_busy_hold():
        pass

    def tk_busy_forget():
        pass


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


class SuccessDialog(tkinter.Toplevel):

    def __init__(self, url, *args, **kwargs):
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
        entry['state'] = 'readonly'     # must be after the insert
        entry.bind('<Control-a>', breaky_select_all)
        entry.bind('<FocusIn>', self._select_all)
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

    def _select_all(self, event=None, breaking=False):
        self._entry.selection_range(0, 'end')
        return ('break' if breaking else None)

    def open_in_browser(self):
        webbrowser.open(self.url)
        self.destroy()

    def copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.url)


class Paste:

    def __init__(self, pastebin_name, code, path):
        self.pastebin_name = pastebin_name
        self.content = code
        self.path = path
        self.please_wait_window = None

    def make_please_wait_window(self):
        window = self.please_wait_window = tkinter.Toplevel()
        window.transient(get_main_window())
        window.title("Pasting...")
        window.geometry('350x150')
        window.resizable(False, False)

        # disable the close button, there's no good way to cancel this
        # forcefully :(
        window.protocol('WM_DELETE_WINDOW', (lambda: None))

        content = ttk.Frame(window)
        content.pack(fill='both', expand=True)

        label = ttk.Label(
            content, font=('', 12, ''),
            text=("Pasting to %s, please wait..." % self.pastebin_name))
        label.pack(expand=True)

        progressbar = ttk.Progressbar(content, mode='indeterminate')
        progressbar.pack(fill='x', padx=15, pady=15)
        progressbar.start()

    def start(self):
        log.debug("starting to paste to %s", self.pastebin_name)
        tk_busy_hold()
        self.make_please_wait_window()
        paste_it = functools.partial(
            pastebins[self.pastebin_name], self.content, self.path)
        utils.run_in_thread(paste_it, self.done_callback)

    def done_callback(self, success, result):
        tk_busy_forget()
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
            log.error("pasting failed\n%s" % result)
            utils.errordialog(
                "Pasting Failed",
                ("Check your internet connection and try again.\n\n" +
                 "Here's the full error message:"),
                monospace_text=result)


def start_pasting(pastebin_name):
    tab = get_tab_manager().select()
    try:
        code = tab.textwidget.get('sel.first', 'sel.last')
    except tkinter.TclError:
        # nothing is selected, pastebin everything
        code = tab.textwidget.get('1.0', 'end - 1 char')

    Paste(pastebin_name, code, tab.path).start()


def setup():
    for name in sorted(pastebins, key=str.casefold):
        assert '/' not in name
        callback = functools.partial(start_pasting, name)
        actions.add_command("Share/" + name, callback, tabtypes=[tabs.FileTab])
