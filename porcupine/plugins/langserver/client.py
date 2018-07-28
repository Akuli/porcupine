import sys
import typing as t
import subprocess
import porcupine

import sansio_lsp_client as lsp
from porcupine.tabs import FileTab

from .utils import (
    tab_uri,
    tab_text,
    tab_position,
    lsp_pos_to_tk_pos,
    find_overlap_start,
)


E = t.TypeVar("E", bound=lsp.Event)


class Client:
    SERVER_COMMANDS = {"Python": [sys.executable, "-m", "pyls"]}

    def __init__(self, tab: FileTab) -> None:
        self._tab = tab
        self._version = 0
        self._unhandled_events = []
        self._lsp_client = lsp.Client()

        self._process = self._start_process()

        def _async_init():
            self._wait_for_event(lsp.Initialized)

            self._lsp_client.did_open(
                lsp.TextDocumentItem(
                    uri=tab_uri(self._tab),
                    languageId=self._tab.filetype.name.lower(),
                    text=tab_text(self._tab),
                    version=self._version,
                )
            )

            self._set_completer()

            # TODO(PurpleMyst): Initialization takes forever. While a printout
            # is fine for development, we probably should add a little spinny
            # thing somewhere.
            print(
                "Language server for {!r} is initialized.".format(
                    self._tab.path
                )
            )

            self._tab.bind(
                "<<FiletypeChanged>>", lambda *_: self._filetype_changed()
            )
            self._tab.textwidget.bind(
                "<<ContentChanged>>", lambda *_: self._content_changed()
            )

        # FIXME(PurpleMyst): Any exceptions that `_async_init` raises
        # shouldn't be ignored.
        # Fun fact: `pass` can't be in place of `...`
        porcupine.utils.run_in_thread(_async_init, lambda *_: ...)

    def _filetype_changed(self):
        self._process = self._start_process()
        self._unhandled_events.clear()

    def _content_changed(self):
        self._version += 1

        # XXX(PurpleMyst): We currently send out the whole document every
        # time anything changes. This sucks. We should fix this, however my
        # library `sansio_lsp_client` currently doesn't support anything but
        # this. I'll fix that pseudo-bug ASAP then we can fix this.
        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=tab_uri(self._tab), version=self._version
            ),
            content_changes=[
                lsp.TextDocumentContentChangeEvent(text=tab_text(self._tab))
            ],
        )

        # TODO(PurpleMyst): Handle `lsp.PublishDiagnostics`.
        # TODO(PurpleMyst): Cancel the request if the user types more before we
        # get a response. This might be *very* hard.

    def _set_completer(self):
        if self._process is None:
            self._tab.completer = None
        else:
            self._tab.completer = lambda *_: self.get_completions()

    def _start_process(self):
        try:
            command = self.SERVER_COMMANDS[self._tab.filetype.name]
        except KeyError:
            return None
        else:
            return subprocess.Popen(
                command, stdout=subprocess.PIPE, stdin=subprocess.PIPE
            )

    # FIXME(PurpleMyst): This method is currently not thread safe. It should be
    # before diagnostics are implemented.
    def _wait_for_event(self, event_type: t.Type[E]) -> E:
        while True:
            self._process.stdin.write(self._lsp_client.send())
            self._process.stdin.flush()

            data = self._process.stdout.readline()
            try:
                events = self._lsp_client.recv(data)
            except lsp.IncompleteResponseError as e:
                if e.missing_bytes is not None:
                    events = self._lsp_client.recv(
                        self._process.stdout.read(e.missing_bytes)
                    )
                else:
                    continue

            self._unhandled_events.extend(events)

            for i, event in enumerate(self._unhandled_events):
                if isinstance(event, event_type):
                    del self._unhandled_events[i]
                    return event

    def get_completions(self) -> t.Iterator[t.Tuple[str, str, str]]:
        self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.VersionedTextDocumentIdentifier(
                    uri=tab_uri(self._tab), version=self._version
                ),
                position=tab_position(self._tab),
            )
        )

        completion_items = self._wait_for_event(
            lsp.Completion
        ).completion_list.items
        for item in completion_items:
            if item.textEdit is not None:
                start = lsp_pos_to_tk_pos(item.textEdit.range.start)
                end = lsp_pos_to_tk_pos(item.textEdit.range.end)
                new_text = item.textEdit.newText
            elif item.insertText is not None:
                line, _ = map(
                    int, self._tab.textwidget.index("insert").split(".")
                )
                start, end = find_overlap_start(
                    line,
                    self._tab.textwidget.get("insert linestart", "insert"),
                    item.insertText,
                )
                new_text = item.insertText
            else:
                raise RuntimeError(
                    "Completion item {!r} had neither textEdit nor insertText".format(
                        item
                    )
                )

            yield (start, end, new_text)
