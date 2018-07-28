import sys
import typing as t
import difflib
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
            self._previous_text = tab_text(self._tab)

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
        self._version = 0
        self._process = self._start_process()
        self._unhandled_events.clear()

    # XXX(PurpleMyst): I'm not sure this method works? I just copy-pasted
    # Akuli's old code and changed it a bit.
    def _calculate_change_events(self, old_code: str, new_code: str) -> lsp.List[lsp.TextDocumentContentChangeEvent]:
        matcher = difflib.SequenceMatcher(a=old_code, b=new_code)
        events = []

        def index_to_position(index: int, text: str) -> lsp.Position:
            line = text.count('\n', 0, index)
            character = index - (text.rfind('\n', 0, index) + 1)
            return lsp.Position(line=line, character=character)

        for (opcode, old_start, old_end, new_start, new_end) in matcher.get_opcodes():
            if opcode == 'equal':
                continue

            replacement = new_code[new_start:new_end]

            how_many_deleted = old_end - old_start
            how_many_inserted = new_end - new_start
            end = new_start + how_many_deleted

            start_pos = index_to_position(new_start, new_code)
            end_pos = index_to_position(end, new_code)

            events.append(lsp.TextDocumentContentChangeEvent.change_range(
                change_start=start_pos,
                change_end=end_pos,
                change_text=replacement,
                old_text=old_code,
            ))
        return events

    def _content_changed(self):
        self._version += 1

        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=tab_uri(self._tab), version=self._version
            ),
            content_changes=self._calculate_change_events(self._previous_text, tab_text(self._tab)),
        )
        self._previous_text = tab_text(self._tab)

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
            # We check if the event is already in `self._unhandled_events`
            # before doing anything so that if a previous call got our event
            # we don't have to wait for more data to be sent over the line.
            for i, event in enumerate(self._unhandled_events):
                if isinstance(event, event_type):
                    del self._unhandled_events[i]
                    return event

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

    def get_completions(self) -> t.Iterator[t.Tuple[str, str, str]]:
        self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.VersionedTextDocumentIdentifier(
                    uri=tab_uri(self._tab), version=self._version
                ),
                position=tab_position(self._tab),
            )
        )

        completion_event = self._wait_for_event(
            lsp.Completion
        )
        completion_items = completion_event.completion_list.items
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
