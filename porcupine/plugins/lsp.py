# langserver plugin

import fcntl
import itertools
import json
import logging
import os
import pprint
import subprocess
from urllib.request import pathname2url

from porcupine import get_tab_manager, tabs, utils
import sansio_lsp_client as lsp

log = logging.getLogger(__name__)


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


class LangServerClient:

    def __init__(self, file_tab, process):
        self._tab = file_tab
        self._process = process
        self._lsp_client = lsp.Client(trace='verbose')
        self._completion_infos = {}
        self._version_counter = itertools.count()
        make_nonblocking(self._process.stdout.fileno())

        # keys are lsp id integers
        # values are porcupine's json info dicts

    def _get_uri(self):
        assert self._tab.path is not None
        return 'file://' + pathname2url(os.path.abspath(self._tab.path))

    def _position_tk2lsp(self, tk_position_string, *, next_column=False):
        # this can't use self._tab.textwidget.index, because it needs to
        # handle text locations that don't exist anymore when text has been
        # deleted
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
            log.warning("lang server process has died")
            return False

        assert received_bytes
        log.debug("got %d bytes of data", len(received_bytes))

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
                log.exception("error while handling langserver event")

        return True

    def _handle_lsp_event(self, lsp_event):
        if isinstance(lsp_event, lsp.Initialized):
            log.info("language server initialized")
            log.debug("capabilities:\n%s",
                      pprint.pformat(lsp_event.capabilities))
            self._lsp_client.did_open(
                lsp.TextDocumentItem(
                    uri=self._get_uri(),
                    languageId='python',
                    text=self._tab.textwidget.get('1.0', 'end - 1 char'),
                    version=0,
                )
            )

        elif isinstance(lsp_event, lsp.Shutdown):
            log.warning("lang server process is shutting down")
            self._lsp_client.exit()

        elif isinstance(lsp_event, lsp.Completion):
            info_dict = self._completion_infos.pop(lsp_event.message_id)
            info_dict['suffixes'] = [
                item.label for item in lsp_event.completion_list.items
            ]
            self._tab.event_generate(
                '<<AutoCompletionResponse>>', data=json.dumps(info_dict))

        elif isinstance(lsp_event, lsp.PublishDiagnostics):
            pass        # TODO

        else:
            raise NotImplementedError(lsp_event)

    def run_stuff(self):
        if self._run_stuff_once():
            get_tab_manager().after(50, self.run_stuff)

    def request_completions(self, event):
        lsp_id = self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=self._get_uri()),
                # lsp line numbering starts at 0, tk line numbering starts at 1
                # both column numberings start at 0
                position=self._position_tk2lsp(
                    self._tab.textwidget.index('insert'),
                    next_column=True,
                ),
            ),
            context=lsp.CompletionContext(
                triggerKind=lsp.CompletionTriggerKind.INVOKED,
            ),
        )
        self._completion_infos[lsp_id] = event.data_json()

    def send_change_events(self, event):
        print(event.data_string)
        change_events = [
            lsp.TextDocumentContentChangeEvent(
                range=lsp.Range(
                    start=self._position_tk2lsp(info['start']),
                    end=self._position_tk2lsp(info['end']),
                ),
                text=info['new_text'],
            )
            for info in event.data_json()
        ]
        print('sending change events', change_events)
        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=self._get_uri(),
                version=next(self._version_counter),
            ),
            content_changes=change_events,
        )


def on_new_tab(event):
    tab = event.data_widget()
    if (    isinstance(tab, tabs.FileTab) and     # noqa
            tab.path is not None and              # noqa
            tab.path.endswith('.py')):            # noqa

        process = subprocess.Popen(
            ['pyls'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        client = LangServerClient(tab, process)
        client.run_stuff()

        utils.bind_with_data(tab, '<<AutoCompletionRequest>>',
                             client.request_completions, add=True)
        utils.bind_with_data(tab.textwidget, '<<ContentChanged>>',
                             client.send_change_events, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
