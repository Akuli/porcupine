# langserver plugin

import fcntl
import shlex
import itertools
import json
import logging
import os
import platform
import pprint
import re
import subprocess
from urllib.request import pathname2url

from porcupine import get_tab_manager, tabs, utils
import sansio_lsp_client as lsp


# 2^10 = 1024 bytes was way too small, and with this chunk size, it still
# sometimes takes two reads to get everything
CHUNK_SIZE = 2**16


# TODO: windows
def make_nonblocking(fileno):
    # this works because we don't use .readilne()
    # https://stackoverflow.com/a/1810703
    old_flags = fcntl.fcntl(fileno, fcntl.F_GETFL)
    new_flags = old_flags | os.O_NONBLOCK
    fcntl.fcntl(fileno, fcntl.F_SETFL, new_flags)


def get_uri(tab):
    assert tab.path is not None
    return 'file://' + pathname2url(os.path.abspath(tab.path))


class LangServer:

    def __init__(self, process, language_id, log):
        self._process = process
        self._language_id = language_id
        self._lsp_client = lsp.Client(trace='verbose')
        self._completion_infos = {}
        self._version_counter = itertools.count()
        self._log = log
        self.tabs_opened = []      # list of tabs

        make_nonblocking(self._process.stdout.fileno())

    def _position_tk2lsp(self, tk_position_string, *, next_column=False):
        # this can't use tab.textwidget.index, because it needs to handle text
        # locations that don't exist anymore when text has been deleted
        line, column = map(int, tk_position_string.split('.'))

        if next_column:
            # lsp wants this for autocompletions? (why lol)
            next_column += 1

        # lsp line numbering starts at 0
        # tk line numbering starts at 1
        # both column numberings start at 0
        return lsp.Position(line=line-1, character=column)

    # returns whether this should be ran again
    def _run_stuff_once(self):
        self._process.stdin.write(self._lsp_client.send())
        self._process.stdin.flush()

        received_bytes = self._process.stdout.read(CHUNK_SIZE)

        if received_bytes is None:
            # no data received
            return True
        elif received_bytes == b'':
            # yes, None and b'' seem to have a different meaning here
            self._log.warning("langserver process crashed")
            return False

        assert received_bytes
        self._log.debug("got %d bytes of data", len(received_bytes))

        try:
            # list() may be needed to make sure we get error immediately, if
            # it is going to error
            lsp_events = list(self._lsp_client.recv(received_bytes))
        except lsp.IncompleteResponseError:
            return True

        for lsp_event in lsp_events:
            try:
                self._handle_lsp_event(lsp_event)
            except Exception:
                self._log.exception("error while handling langserver event")

        return True

    def _send_tab_opened_message(self, tab):
        self._lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=get_uri(tab),
                languageId=self._language_id,
                text=tab.textwidget.get('1.0', 'end - 1 char'),
                version=0,
            )
        )

    def _handle_lsp_event(self, lsp_event):
        if isinstance(lsp_event, lsp.Initialized):
            self._log.info("langserver initialized, capabilities:\n%s",
                           pprint.pformat(lsp_event.capabilities))

            for tab in self.tabs_opened:
                self._send_tab_opened_message(tab)

        elif isinstance(lsp_event, lsp.Shutdown):
            self._log.warning("langserver process shutting down")
            self._lsp_client.exit()

        elif isinstance(lsp_event, lsp.Completion):
            info_dict = self._completion_infos.pop(lsp_event.message_id)
            tab = info_dict.pop('tab')

            # this is "open to interpretation", as the lsp spec says
            # TODO: use textEdit when available (requires some refactoring)
            current_line = tab.textwidget.get('insert linestart', 'insert')
            prefix_len = len(re.fullmatch(r'.*?(\w*)', current_line).group(1))

            info_dict['suffixes'] = [
                (item.insertText or item.label)[prefix_len:]
                for item in sorted(
                    lsp_event.completion_list.items,
                    key=(lambda item: item.sortText or item.label),
                )
            ]
            tab.event_generate(
                '<<AutoCompletionResponse>>', data=json.dumps(info_dict))

        elif isinstance(lsp_event, lsp.PublishDiagnostics):
            pass        # TODO

        else:
            raise NotImplementedError(lsp_event)

    def run_stuff(self):
        if self._run_stuff_once():
            get_tab_manager().after(50, self.run_stuff)

    def open_tab(self, tab):
        self.tabs_opened.append(tab)
        if self._lsp_client.state == lsp.ClientState.NORMAL:
            self._send_tab_opened_message(tab)

    # TODO: closing tabs

    def request_completions(self, event):
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            self._log.warning(
                "autocompletions requested but langserver state == %r",
                self._lsp_client.state)
            return

        tab = event.widget
        lsp_id = self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=get_uri(tab)),
                # lsp line numbering starts at 0, tk line numbering starts at 1
                # both column numberings start at 0
                position=self._position_tk2lsp(
                    tab.textwidget.index('insert'), next_column=True
                ),
            ),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED,
            ),
        )

        assert lsp_id not in self._completion_infos
        self._completion_infos[lsp_id] = event.data_json()
        self._completion_infos[lsp_id]['tab'] = tab

    def send_change_events(self, event):
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            self._log.warning(
                "not sending change events because langserver state == %r",
                self._lsp_client.state)
            return

        tab = event.widget.master
        assert isinstance(tab, tabs.FileTab)
        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=get_uri(tab),
                version=next(self._version_counter),
            ),
            content_changes=[
                lsp.TextDocumentContentChangeEvent(
                    range=lsp.Range(
                        start=self._position_tk2lsp(info['start']),
                        end=self._position_tk2lsp(info['end']),
                    ),
                    text=info['new_text'],
                )
                for info in event.data_json()
            ],
        )


langservers = {}    # keys are filetype objects


def get_lang_server(filetype):
    if filetype is None:
        return None

    try:
        return langservers[filetype]
    except KeyError:
        pass

    if not (filetype.langserver_command and filetype.langserver_language_id):
        logging.getLogger(__name__).info(
            "langserver not configured for filetype " + filetype.name)
        return None

    log = logging.getLogger(
        __name__ + '.' + filetype.langserver_language_id)

    # avoid shell=True on non-windows to get process.pid to do the right thing
    #
    # with shell=True it's the pid of the shell, not the pid of the program
    #
    # on windows, there is no shell and it's all about whether to quote or not
    if platform.system() == 'Windows':
        shell = True
        command = filetype.langserver_command
    else:
        shell = False
        command = shlex.split(filetype.langserver_command)

    try:
        process = subprocess.Popen(
            command, shell=shell,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError):
        log.exception(
            "cannot start langserver process with command '%s'",
            filetype.langserver_command)
        return None

    log.info("Langserver process started with command '%s', PID %d",
             filetype.langserver_command, process.pid)

    langserver = LangServer(
        process, filetype.langserver_language_id, log)
    langserver.run_stuff()
    langservers[filetype] = langserver
    return langserver


def on_new_tab(event):
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        langserver = get_lang_server(tab.filetype)
        if langserver is None:
            return

        utils.bind_with_data(tab, '<<AutoCompletionRequest>>',
                             langserver.request_completions, add=True)
        utils.bind_with_data(tab.textwidget, '<<ContentChanged>>',
                             langserver.send_change_events, add=True)
        langserver.open_tab(tab)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
