# FIXME: this is way too python-specific :(

import functools
import logging
import os
import socket
import tkinter
from tkinter import ttk
import webbrowser

try:
    import requests
except ImportError:
    requests = None

import porcupine
from porcupine import tabs, utils
from porcupine import __version__ as _porcupine_version
try:
    from porcupine.plugins import pythonprompt
except ImportError:
    pythonprompt = None


log = logging.getLogger(__name__)

# this makes the "Run" menu always appear before the "Pastebin to" menu,
# most people need the run menu more than the pastebin menu
setup_after = ['run']

_pastebins = {}


def pastebin(name):
    def inner(function):
        _pastebins[name] = function
        return function

    return inner


# the origin argument is always a path to a file, None or '>>>'
@pastebin("termbin.com")
def paste_to_termbin(code, origin):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(('termbin.com', 9999))
        sock.send(code.encode('utf-8'))
        url = sock.recv(1024)
        if url.startswith(b'Use netcat'):
            raise RuntimeError("sending to termbin failed (got %r)" % url)

        # today termbin adds zero bytes to my URL's 0_o it hasn't done
        # it before
        # i've never seen it add \r but i'm not surprised if it adds it
        return url.rstrip(b'\n\r\0').decode('ascii')


if requests is not None:
    # TODO: add porcupine version here if there will be a version number
    session = requests.Session()
    session.headers['User-Agent'] = "Porcupine/%s" % _porcupine_version

    @pastebin("dpaste.com")
    def paste_to_dpaste_com(code, origin):
        # dpaste's syntax highlighting for interactive sessions grays out
        # the output annoyingly :( we'll just use the python3 syntax for
        # everything
        response = session.post('http://dpaste.com/api/v2/', data={
            'content': code,
            'syntax': 'python3',
        })
        response.raise_for_status()
        return response.text.strip()

    @pastebin("dpaste.de")
    def paste_to_dpaste_de(code, origin):
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
    def paste_to_ghostbin(code, origin):
        # docs: https://ghostbin.com/paste/p3qcy
        if origin == '>>>':
            syntax = 'pycon'
        else:
            syntax = 'python3'

        response = session.post(
            'https://ghostbin.com/paste/new',
            data={'text': code},
            params={
                'expire': '30d',
                'lang': syntax,
            },
        )
        response.raise_for_status()
        return response.url

    @pastebin("GitHub Gist")
    def paste_to_github_gist(code, origin):
        # docs: https://developer.github.com/v3/gists/#create-a-gist
        if origin == '>>>':
            gist_file = 'python-session.txt'      # this sucks :(
        elif origin is None:
            gist_file = 'new-file.py'
        else:
            gist_file = os.path.basename(origin)

        response = session.post('https://api.github.com/gists', json={
            'public': False,
            'files': {gist_file: {'content': code}},
        })
        response.raise_for_status()
        return response.json()['html_url']

    @pastebin("Paste ofCode")
    def paste_to_paste_ofcode(code, origin):
        if origin == '>>>':
            syntax = 'pycon'
        else:
            syntax = 'python3'
        response = session.post('http://paste.ofcode.org/', data={
            'code': code,
            'language': syntax,
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
            ("Open in browser", self._open_browser),
            ("Copy to clipboard", self._to_clipboard),
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

    def _open_browser(self):
        webbrowser.open(self.url)
        self.destroy()

    def _to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.url)


class Paste:

    def __init__(self, pastebin_name, code, origin):
        self.pastebin_name = pastebin_name
        self.content = code
        self.origin = origin
        self.please_wait_window = None

    def make_please_wait_window(self):
        window = self.please_wait_window = tkinter.Toplevel()
        window.transient(porcupine.get_main_window())
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
        window = porcupine.get_main_window()
        busy_status = window.tk.call('tk', 'busy', 'status', window)
        if window.getboolean(busy_status):
            # we are already pasting something somewhere or something
            # else is being done
            log.info("'tk busy status %s' returned 1", window)
            return

        log.debug("starting to paste to %s", self.pastebin_name)

        window.tk.call('tk', 'busy', 'hold', window)
        self.make_please_wait_window()
        paste_it = functools.partial(
            _pastebins[self.pastebin_name], self.content, self.origin)
        utils.run_in_thread(paste_it, self.done_callback)

    def done_callback(self, success, result):
        window = porcupine.get_main_window()
        window.tk.call('tk', 'busy', 'forget', window)
        self.please_wait_window.destroy()

        if success:
            log.info("pasting succeeded")
            dialog = SuccessDialog(result)
            dialog.title("Pasting Succeeded")
            dialog.geometry('450x150')
            dialog.transient(window)
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
    tab = porcupine.get_tab_manager().current_tab
    try:
        code = tab.textwidget.get('sel.first', 'sel.last')
    except tkinter.TclError:
        # nothing is selected, pastebin everything
        code = tab.textwidget.get('1.0', 'end - 1 char')

    if isinstance(tab, tabs.FileTab):
        origin = tab.path
    else:
        origin = '>>>'      # FIXME

    Paste(pastebin_name, code, origin).start()


def setup():
    tabtypes = [tabs.FileTab]
    if pythonprompt is not None:
        tabtypes.append(pythonprompt.PromptTab)

    for name in sorted(_pastebins, key=str.casefold):
        assert '/' not in name, "porcupine.add_action() needs to be fixed"
        callback = functools.partial(start_pasting, name)
        porcupine.add_action(callback, "Share/" + name, tabtypes=tabtypes)
