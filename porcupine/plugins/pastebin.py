import functools
import json
import logging
import os
import socket
import tkinter as tk
from tkinter import ttk
import webbrowser

try:
    import requests
except ImportError:
    requests = None

from porcupine import tabs, utils
try:
    from porcupine.plugins import pythonprompt
except ImportError:
    pythonprompt = None

log = logging.getLogger(__name__)

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
        return url.decode('utf-8').strip()


if requests is not None:
    # TODO: add porcupine version here if there will be a version number
    session = requests.Session()
    session.headers['User-Agent'] = "Porcupine"

    # there's also a dpaste.de, must not confuse this with it
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

        # TODO: can we do json={...} instead?
        response = session.post(
            'https://api.github.com/gists', data=json.dumps({
                'public': False,
                'files': {gist_file: {'content': code}},
            })
        )
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


class Paste:

    def __init__(self, editorwindow, pastebin_name, code, origin):
        self.editorwindow = editorwindow
        self.pastebin_name = pastebin_name
        self.content = code
        self.origin = origin
        self.please_wait_window = None

    def _do_nothing(self):
        pass

    def make_please_wait_window(self):
        window = self.please_wait_window = tk.Toplevel()
        window.transient(self.editorwindow)

        label = tk.Label(
            window, font=('', 12, ''),
            text=("Pasting to %s, please wait..." % self.pastebin_name))
        label.pack(expand=True)

        progressbar = ttk.Progressbar(window, mode='indeterminate')
        progressbar.pack(fill='x', padx=15, pady=15)
        progressbar.start()

        window.protocol('WM_DELETE_WINDOW', self._do_nothing)
        window.title("Pasting...")
        window.geometry('350x150')
        window.resizable(False, False)

    def start(self):
        busy_status = self.editorwindow.tk.call(
            'tk', 'busy', 'status', self.editorwindow)
        if self.editorwindow.getboolean(busy_status):
            # we are already pasting something somewhere or something
            # else is being done
            log.info("'tk busy status %s' returned 1", self.editorwindow)
            return

        log.debug("starting to paste to %s", self.pastebin_name)

        self.editorwindow.tk.call('tk', 'busy', 'hold', self.editorwindow)
        self.make_please_wait_window()
        paste_it = functools.partial(
            _pastebins[self.pastebin_name], self.content, self.origin)
        utils.run_in_thread(paste_it, self.done_callback)

    def _to_clipboard(self, url):
        self.editorwindow.clipboard_clear()
        self.editorwindow.clipboard_append(url)

    def show_url(self, url):
        dialog = tk.Toplevel()
        dialog.title("Pasting Succeeded")

        label = tk.Label(dialog, text="Here's your URL:")
        label.place(relx=0.5, rely=0.15, anchor='center')

        def select_all(event=None, breaking=False):
            entry.selection_range(0, 'end')
            return ('break' if breaking else None)

        entry = tk.Entry(dialog, justify='center')
        entry.place(relx=0.5, rely=0.4, anchor='center', relwidth=1)
        entry.insert(0, url)
        entry['state'] = 'readonly'     # must be after the insert
        entry.bind('<Control-a>', functools.partial(select_all, breaking=True))
        entry.bind('<FocusIn>', select_all)
        select_all()

        button_info = [
            ("Open in browser", functools.partial(webbrowser.open, url)),
            ("Copy to clipboard", functools.partial(self._to_clipboard, url)),
            ("Close this dialog", dialog.destroy),
        ]
        buttonframe = tk.Frame(dialog)
        buttonframe.place(relx=0.5, rely=0.8, anchor='center', relwidth=1)
        for text, callback in button_info:
            button = tk.Button(buttonframe, text=text, command=callback)
            button.pack(side='left', expand=True)

        dialog.geometry('450x150')
        dialog.transient(utils.get_root())
        dialog.wait_window()

    def done_callback(self, success, result):
        self.editorwindow.tk.call('tk', 'busy', 'forget', self.editorwindow)
        self.please_wait_window.destroy()

        if success:
            log.info("pasting succeeded")
            self.show_url(result)
        else:
            # result is the traceback as a string
            log.error("pasting failed\n%s" % result)
            utils.errordialog(
                "Pasting Failed",
                "Check your internet connection and try again.\n\n"
                + "Here's the full error message:",
                monospace_text=result)


def setup(editor):
    editorwindow = utils.get_window(editor)

    def start_pasting(pastebin_name):
        tab = editor.tabmanager.current_tab
        code = tab.textwidget.get('1.0', 'end-1c')
        if isinstance(tab, tabs.FileTab):
            origin = tab.path
        else:
            origin = '>>>'

        paste = Paste(editorwindow, pastebin_name, code, origin)
        paste.start()

    tabtypes = [tabs.FileTab]
    if pythonprompt is not None:
        tabtypes.append(pythonprompt.PromptTab)

    for name in sorted(_pastebins, key=str.casefold):
        callback = functools.partial(start_pasting, name)
        editor.add_action(callback, "Pastebin to/" + name, tabtypes=tabtypes)
