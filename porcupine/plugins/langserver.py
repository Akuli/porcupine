"""Langserver support for autocompletions."""
# TODO: CompletionProvider
# TODO: error reporting in gui somehow
from __future__ import annotations

import dataclasses
import itertools
import logging
import os
import pprint
import queue
import re
import signal
import subprocess
import sys
import threading
from functools import partial
from pathlib import Path
from typing import IO, Any, Iterator, NamedTuple, Optional

if sys.platform != "win32":
    import fcntl

import sansio_lsp_client as lsp

from porcupine import get_tab_manager, tabs, textutils, utils
from porcupine.plugins import autocomplete, hover, jump_to_definition, python_venv, underlines

global_log = logging.getLogger(__name__)

# Before autocomplete: use this plugin's autocompleter, so must bind first
# After underlines: when hovering something underlined, don't ask langserver what to show
# After python_venv: needed for python_venv.get_venv() to work
setup_before = ["autocomplete"]
setup_after = ["python_venv", "underlines"]


# 1024 bytes was way too small, and with this chunk size, it
# still sometimes takes two reads to get everything (that's fine)
CHUNK_SIZE = 64 * 1024


class NonBlockingIO:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process

        # Reads can obviously block, but flushing can block too, see #635
        # Nonblock flags don't help with writing, it raises error if it would block
        self._write_queue: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._write_queue_to_stdin, daemon=True).start()

        if sys.platform == "win32":
            self._read_queue: queue.Queue[bytes] = queue.Queue()
            self._reader_thread = threading.Thread(target=self._stdout_to_read_queue, daemon=True)
            self._reader_thread.start()
        else:
            # this works because we don't use .readline()
            # https://stackoverflow.com/a/1810703
            assert process.stdout is not None
            fileno = process.stdout.fileno()
            old_flags = fcntl.fcntl(fileno, fcntl.F_GETFL)
            new_flags = old_flags | os.O_NONBLOCK
            fcntl.fcntl(fileno, fcntl.F_SETFL, new_flags)

    def _write_queue_to_stdin(self) -> None:
        while self._process.poll() is None:
            # Why timeout: if process dies and no more to write, stop soon
            try:
                chunk = self._write_queue.get(timeout=5)
            except queue.Empty:  # timed out
                continue

            # Process can exit while waiting, but clean shutdown involves
            # writing messages before the process exits, so here it should
            # be still alive
            assert self._process.stdin is not None
            self._process.stdin.write(chunk)
            self._process.stdin.flush()

    if sys.platform == "win32":

        def _stdout_to_read_queue(self) -> None:
            while True:
                # for whatever reason, nothing works unless i go ONE BYTE at a
                # time.... this is a piece of shit
                #
                # TODO: read1() method?
                assert self._process.stdout is not None
                one_fucking_byte = self._process.stdout.read(1)
                if not one_fucking_byte:
                    break
                self._read_queue.put(one_fucking_byte)

    # Return values:
    #   - nonempty bytes object: data was read
    #   - empty bytes object: process exited
    #   - None: no data to read
    def read(self) -> bytes | None:
        if sys.platform == "win32":
            buf = bytearray()
            while True:
                try:
                    buf += self._read_queue.get(block=False)
                except queue.Empty:
                    break

            if self._reader_thread.is_alive() and not buf:
                return None
            return bytes(buf)

        else:
            assert self._process.stdout is not None
            return self._process.stdout.read(CHUNK_SIZE)

    def write(self, bytez: bytes) -> None:
        self._write_queue.put(bytez)


def completion_item_doc_contains_label(doc: str, label: str) -> bool:
    # this used to be doc.startswith(label), but see issue #67
    label = label.strip()
    if "(" in label:
        prefix = label.strip().split("(")[0] + "("
    else:
        prefix = label.strip()
    return doc.startswith(prefix)


def get_completion_item_doc(item: lsp.CompletionItem) -> str:
    if not item.documentation:
        return item.label

    if isinstance(item.documentation, lsp.MarkupContent):
        result = item.documentation.value
    else:
        result = item.documentation

    # try this with clangd
    #
    #    // comment
    #    void foo(int x, char c) { }
    #
    #    int main(void)
    #    {
    #        fo<Tab>
    #    }
    if not completion_item_doc_contains_label(result, item.label):
        result = item.label.strip() + "\n\n" + result
    return result


def exit_code_string(exit_code: int) -> str:
    if exit_code >= 0:
        return f"exited with code {exit_code}"

    signal_number = abs(exit_code)
    result = f"was killed by signal {signal_number}"

    try:
        result += " (" + signal.Signals(signal_number).name + ")"
    except ValueError:
        # unknown signal, e.g. signal.SIGRTMIN + 5
        pass

    return result


def _position_tk2lsp(tk_position: str | list[int]) -> lsp.Position:
    # this can't use tab.textwidget.index, because it needs to handle text
    # locations that don't exist anymore when text has been deleted
    if isinstance(tk_position, str):
        line, column = map(int, tk_position.split("."))
    else:
        line, column = tk_position

    # lsp line numbering starts at 0
    # tk line numbering starts at 1
    # both column numberings start at 0
    return lsp.Position(line=line - 1, character=column)


def _position_lsp2tk(lsp_position: lsp.Position) -> str:
    return f"{lsp_position.line + 1}.{lsp_position.character}"


# TODO: do this better in sansio-lsp-client
def _get_jump_paths_and_ranges(
    locations: list[lsp.Location | lsp.LocationLink] | lsp.Location | None,
) -> Iterator[tuple[Path, lsp.Range]]:
    if locations is None:
        locations = []
    if not isinstance(locations, list):
        locations = [locations]

    for location in locations:
        assert not isinstance(location, lsp.LocationLink)  # TODO
        yield (utils.file_url_to_path(location.uri), location.range)


def _get_diagnostic_string(diagnostic: lsp.Diagnostic) -> str:
    if diagnostic.source is None:
        assert diagnostic.message is not None  # TODO
        return diagnostic.message
    return f"{diagnostic.source}: {diagnostic.message}"


# TODO: should handle better in sansio-lsp-client
def _get_hover_string(
    hover_contents: list[lsp.MarkedString | str] | lsp.MarkedString | lsp.MarkupContent | str,
) -> str:
    if isinstance(hover_contents, (lsp.MarkedString, lsp.MarkupContent)):
        return hover_contents.value
    if isinstance(hover_contents, list):
        return "\n\n".join(_get_hover_string(item) for item in hover_contents)
    return hover_contents


def _substitute_python_venv_recursively(obj: object, venv: Path | None) -> Any:
    if isinstance(obj, list):
        return [_substitute_python_venv_recursively(item, venv) for item in obj]
    if isinstance(obj, dict):
        return {key: _substitute_python_venv_recursively(value, venv) for key, value in obj.items()}
    if isinstance(obj, str):
        # This doesn't account for weird formatting tricks, but those aren't useful here anyway
        if "{python_venv}" in obj and venv is None:
            return None
        return obj.format(python_venv=str(venv))
    return obj


@dataclasses.dataclass
class LangServerConfig:
    command: str
    language_id: str
    settings: Any = dataclasses.field(default_factory=dict)


class LangServerId(NamedTuple):
    command: str
    project_root: Path


class LangServer:
    def __init__(
        self,
        process: subprocess.Popen[bytes],
        the_id: LangServerId,
        log: logging.LoggerAdapter[logging.Logger],
        config: LangServerConfig,
    ) -> None:
        self._process = process
        self._config = config
        self._id = the_id  # TODO: replace with config
        self._lsp_client = lsp.Client(trace="verbose", root_uri=the_id.project_root.as_uri())

        self._autocompletion_requests: dict[lsp.Id, tuple[tabs.FileTab, autocomplete.Request]] = {}
        self._jump2def_requests: dict[lsp.Id, tabs.FileTab] = {}
        self._hover_requests: dict[lsp.Id, tuple[tabs.FileTab, str]] = {}

        self._version_counter = itertools.count()
        self.log = log
        self.tabs_opened: set[tabs.FileTab] = set()
        self._is_shutting_down_cleanly = False

        self._io = NonBlockingIO(process)

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__}: "
            f"PID {self._process.pid}, "
            f"{self._id}, "
            f"{len(self.tabs_opened)} tabs opened>"
        )

    def _is_in_langservers(self) -> bool:
        # This returns False if a langserver died and another one with the same
        # id was launched.
        return langservers.get(self._id, None) is self

    def _get_removed_from_langservers(self) -> None:
        # this is called more than necessary to make sure we don't end up with
        # funny issues caused by unusable langservers
        if self._is_in_langservers():
            self.log.debug("getting removed from langservers")
            del langservers[self._id]

    def _ensure_langserver_process_quits_soon(self) -> None:
        exit_code = self._process.poll()
        if exit_code is None:
            if self._lsp_client.state == lsp.ClientState.EXITED:
                # process still running, but will exit soon. Let's make sure
                # to log that when it happens so that if it doesn't exit for
                # whatever reason, then that will be visible in logs.
                self.log.debug("langserver process should stop soon")
                get_tab_manager().after(500, self._ensure_langserver_process_quits_soon)
                return

            # langserver doesn't want to exit, let's kill it
            self.log.warning(
                f"killing langserver process {self._process.pid} "
                f"because stdout has closed for some reason"
            )

            if self._process.poll() is None:  # process still alive
                try:
                    self._process.kill()
                except ProcessLookupError:
                    # died between wait and kill (I think that's why this happens)
                    pass
            exit_code = self._process.wait()

        if self._is_shutting_down_cleanly:
            self.log.info(f"langserver process terminated, {exit_code_string(exit_code)}")
        else:
            self.log.error(
                f"langserver process terminated unexpectedly, {exit_code_string(exit_code)}"
            )

        self._get_removed_from_langservers()

    # returns whether this should be ran again
    def _run_stuff_once(self) -> bool:
        self._io.write(self._lsp_client.send())
        received_bytes = self._io.read()

        # yes, None and b'' have a different meaning here
        if received_bytes is None:
            # no data received
            return True
        elif received_bytes == b"":
            # stdout or langserver socket is closed. Communicating with the
            # langserver process is impossible, so this LangServer object and
            # the process are useless.
            #
            # TODO: try to restart the langserver process?
            self._ensure_langserver_process_quits_soon()
            return False

        assert received_bytes
        self.log.debug(f"got {len(received_bytes)} bytes of data")

        try:
            for lsp_event in self._lsp_client.recv(received_bytes):
                self._handle_lsp_event(lsp_event)
        except Exception as e:
            # A hack elsewhere in this file causes an event that sansio-lsp-client
            # doesn't understand. To find it, ctrl+f hack.
            if isinstance(e, NotImplementedError) and "workspace/didChangeConfiguration" in str(e):
                self.log.debug(f"got NotImplementedError from hacky code as expected: {e}")
            else:
                self.log.exception("error while handling langserver event")

        return True

    def _send_tab_opened_message(self, tab: tabs.FileTab) -> None:
        config = tab.settings.get("langserver", Optional[LangServerConfig])
        assert tab.path is not None

        self._lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=tab.path.as_uri(),
                languageId=config.language_id,
                text=tab.textwidget.get("1.0", "end - 1 char"),
                version=next(self._version_counter),
            )
        )

    def _handle_lsp_event(self, lsp_event: lsp.Event) -> None:
        self.log.debug(f"handling event: {lsp_event}")

        if isinstance(lsp_event, lsp.Shutdown):
            self.log.debug("langserver sent Shutdown event")
            self._lsp_client.exit()
            self._get_removed_from_langservers()
            return

        if isinstance(lsp_event, lsp.LogMessage):
            # most langservers seem to use stdio instead of this
            loglevel_dict = {
                lsp.MessageType.LOG: logging.DEBUG,
                lsp.MessageType.INFO: logging.INFO,
                lsp.MessageType.WARNING: logging.WARNING,
                lsp.MessageType.ERROR: logging.ERROR,
            }
            self.log.log(
                loglevel_dict[lsp_event.type], f"message from langserver: {lsp_event.message}"
            )
            return

        # rest of these need the langserver to be active
        if not self._is_in_langservers():
            self.log.info(f"ignoring event because langserver is shutting down: {lsp_event}")
            return

        if isinstance(lsp_event, lsp.Initialized):
            self.log.info(
                "langserver initialized, capabilities:\n" + pprint.pformat(lsp_event.capabilities)
            )

            for tab in self.tabs_opened:
                self._send_tab_opened_message(tab)

            # TODO: this is a terrible hack:
            #   - This causes an error because sansio-lsp-client doesn't
            #     officially support workspace/didChangeConfiguration yet.
            #   - This doesn't refresh as venv changes.
            self._lsp_client._send_request(
                "workspace/didChangeConfiguration",
                {
                    "settings": _substitute_python_venv_recursively(
                        self._config.settings, python_venv.get_venv(self._id.project_root)
                    )
                },
            )
            return

        if isinstance(lsp_event, lsp.Completion):
            tab, req = self._autocompletion_requests.pop(lsp_event.message_id)
            if tab not in self.tabs_opened:
                # I wouldn't be surprised if some langserver sent completions to closed tabs
                self.log.debug(f"Completion sent to closed tab: {lsp_event}")
                return

            # this is "open to interpretation", as the lsp spec says
            # TODO: use textEdit when available (need to find langserver that
            #       gives completions with textEdit for that to work)
            before_cursor = tab.textwidget.get(f"{req.cursor_pos} linestart", req.cursor_pos)
            match = re.fullmatch(r".*?(\w*)", before_cursor)
            assert match is not None
            prefix_len = len(match.group(1))

            assert lsp_event.completion_list is not None
            tab.event_generate(
                "<<AutoCompletionResponse>>",
                data=autocomplete.Response(
                    id=req.id,
                    completions=[
                        autocomplete.Completion(
                            display_text=item.label,
                            replace_start=tab.textwidget.index(
                                f"{req.cursor_pos} - {prefix_len} chars"
                            ),
                            replace_end=req.cursor_pos,
                            replace_text=item.insertText or item.label,
                            # TODO: is slicing necessary here?
                            filter_text=(item.filterText or item.insertText or item.label)[
                                prefix_len:
                            ],
                            documentation=get_completion_item_doc(item),
                        )
                        for item in sorted(
                            lsp_event.completion_list.items,
                            key=(lambda item: item.sortText or item.label),
                        )
                    ],
                ),
            )
            return

        if isinstance(lsp_event, lsp.PublishDiagnostics):
            matching_tabs = [
                tab
                for tab in self.tabs_opened
                if tab.path is not None and tab.path.as_uri() == lsp_event.uri
            ]
            if not matching_tabs:
                # Some langservers send diagnostics to closed tabs
                self.log.debug(f"PublishDiagnostics sent to closed tab: {lsp_event}")
                return
            [tab] = matching_tabs

            tab.event_generate(
                "<<SetUnderlines>>",
                data=underlines.Underlines(
                    id="diagnostics",
                    underline_list=[
                        underlines.Underline(
                            start=_position_lsp2tk(diagnostic.range.start),
                            end=_position_lsp2tk(diagnostic.range.end),
                            message=_get_diagnostic_string(diagnostic),
                            # TODO: there are plenty of other severities than ERROR and WARNING
                            color=(
                                "red"
                                if diagnostic.severity == lsp.DiagnosticSeverity.ERROR
                                else "orange"
                            ),
                        )
                        for diagnostic in sorted(
                            lsp_event.diagnostics,
                            # error red underlines should be shown over orange warning underlines
                            key=(lambda diagn: diagn.severity or lsp.DiagnosticSeverity.WARNING),
                            reverse=True,
                        )
                    ],
                ),
            )
            return

        if isinstance(lsp_event, lsp.Definition):
            assert lsp_event.message_id is not None  # TODO: fix in sansio-lsp-client
            requesting_tab = self._jump2def_requests.pop(lsp_event.message_id)

            if requesting_tab in get_tab_manager().tabs():
                requesting_tab.event_generate(
                    "<<JumpToDefinitionResponse>>",
                    data=jump_to_definition.Response(
                        [
                            jump_to_definition.LocationRange(
                                file_path=str(path),
                                start=_position_lsp2tk(range.start),
                                end=_position_lsp2tk(range.end),
                            )
                            for path, range in _get_jump_paths_and_ranges(lsp_event.result)
                        ]
                    ),
                )
            else:
                self.log.debug("not jumping to definition, tab was closed")
            return

        if isinstance(lsp_event, lsp.Hover):
            assert lsp_event.message_id is not None  # TODO: fix in sansio-lsp-client
            requesting_tab, location = self._hover_requests.pop(lsp_event.message_id)

            if requesting_tab in get_tab_manager().tabs():
                requesting_tab.textwidget.event_generate(
                    "<<HoverResponse>>",
                    data=hover.Response(location, _get_hover_string(lsp_event.contents)),
                )
            else:
                self.log.debug("not showing hover, tab was closed")
            return

        # str(lsp_event) or just lsp_event won't show the type
        raise NotImplementedError(repr(lsp_event))

    def run_stuff(self) -> None:
        if self._run_stuff_once():
            get_tab_manager().after(50, self.run_stuff)

    def open_tab(self, tab: tabs.FileTab) -> None:
        assert tab not in self.tabs_opened
        self.tabs_opened.add(tab)
        self.log.debug("tab opened")
        if self._lsp_client.state == lsp.ClientState.NORMAL:
            self._send_tab_opened_message(tab)

    def forget_tab(self, tab: tabs.FileTab, *, may_shutdown: bool = True) -> None:
        if not self._is_in_langservers():
            self.log.debug(
                "a tab was closed, but langserver process is no longer running (maybe it crashed?)"
            )
            return

        self.tabs_opened.remove(tab)
        self.log.debug("tab closed")

        if may_shutdown and not self.tabs_opened:
            self.log.info("no more open tabs, shutting down")
            self._is_shutting_down_cleanly = True
            self._get_removed_from_langservers()

            if self._lsp_client.state == lsp.ClientState.NORMAL:
                self._lsp_client.shutdown()
            else:
                # it was never fully started
                self._process.kill()

    def request_completions(self, tab: tabs.FileTab, event: utils.EventWithData) -> None:
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            self.log.warning(
                f"autocompletions requested but langserver state == {self._lsp_client.state!r}"
            )
            return

        assert tab.path is not None
        request = event.data_class(autocomplete.Request)
        lsp_id = self._lsp_client.completion(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=tab.path.as_uri()),
                position=_position_tk2lsp(request.cursor_pos),
            ),
            context=lsp.CompletionContext(
                # FIXME: this isn't always the case, porcupine can also trigger
                #        it automagically
                triggerKind=lsp.CompletionTriggerKind.INVOKED
            ),
        )

        assert lsp_id not in self._autocompletion_requests
        self._autocompletion_requests[lsp_id] = (tab, request)

    def request_jump_to_definition(self, tab: tabs.FileTab) -> None:
        self.log.info(f"Jump to definition requested: {tab.path} {self._lsp_client.state}")
        if tab.path is not None and self._lsp_client.state == lsp.ClientState.NORMAL:
            request_id = self._lsp_client.definition(
                lsp.TextDocumentPosition(
                    textDocument=lsp.TextDocumentIdentifier(uri=tab.path.as_uri()),
                    position=_position_tk2lsp(tab.textwidget.index("insert")),
                )
            )
            self._jump2def_requests[request_id] = tab

    def request_hover(self, tab: tabs.FileTab, location: str) -> None:
        self.log.info(f"Hover requested: {tab.path} {self._lsp_client.state}")
        if tab.path is not None and self._lsp_client.state == lsp.ClientState.NORMAL:
            request_id = self._lsp_client.hover(
                lsp.TextDocumentPosition(
                    textDocument=lsp.TextDocumentIdentifier(uri=tab.path.as_uri()),
                    position=_position_tk2lsp(location),
                )
            )
            self._hover_requests[request_id] = (tab, location)

    def send_change_events(self, tab: tabs.FileTab, changes: textutils.Changes) -> None:
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            # The langserver will receive the actual content of the file once
            # it starts.
            self.log.debug(
                f"not sending change events because langserver state == {self._lsp_client.state!r}"
            )
            return

        assert tab.path is not None
        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=tab.path.as_uri(), version=next(self._version_counter)
            ),
            content_changes=[
                lsp.TextDocumentContentChangeEvent(
                    range=lsp.Range(
                        start=_position_tk2lsp(change.start), end=_position_tk2lsp(change.end)
                    ),
                    text=change.new_text,
                )
                for change in changes.change_list
            ],
        )


langservers: dict[LangServerId, LangServer] = {}


def stream_to_log(stream: IO[bytes], log: logging.LoggerAdapter[logging.Logger]) -> None:
    for line_bytes in stream:
        line = line_bytes.rstrip(b"\r\n").decode("utf-8", errors="replace")
        log.info(f"langserver logged: {line}")


def get_lang_server(tab: tabs.FileTab) -> LangServer | None:
    if tab.path is None:
        return None

    config = tab.settings.get("langserver", Optional[LangServerConfig])
    if config is None:
        return None
    assert isinstance(config, LangServerConfig)

    project_root = utils.find_project_root(tab.path)
    the_id = LangServerId(config.command, project_root)
    try:
        return langservers[the_id]
    except KeyError:
        pass

    command = utils.format_command(config.command, {"porcupine_python": utils.python_executable})
    global_log.info(f"Running command: {command}")

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,  # log messages
            **utils.subprocess_kwargs,
        )
    except (OSError, subprocess.CalledProcessError):
        global_log.exception(f"failed to start langserver with command {config.command!r}")
        return None

    log = logging.LoggerAdapter(global_log, {})
    log.process = lambda msg, kwargs: (f"(PID={process.pid}) {msg}", kwargs)  # type: ignore
    log.info(
        f"Langserver process started with command '{config.command}', project root '{project_root}'"
    )

    assert process.stderr is not None
    threading.Thread(target=stream_to_log, args=[process.stderr, log], daemon=True).start()

    langserver = LangServer(process, the_id, log, config)
    langserver.run_stuff()
    langservers[the_id] = langserver
    return langserver


# Switch the tab to another langserver, starting one if needed
def switch_langservers(
    tab: tabs.FileTab, called_because_path_changed: bool, junk: object = None
) -> None:
    old = next(
        (langserver for langserver in langservers.values() if tab in langserver.tabs_opened), None
    )
    new = get_lang_server(tab)

    if old is not None and new is not None and old is new and called_because_path_changed:
        old.log.info("Path changed, closing and reopening the tab")
        old.forget_tab(tab, may_shutdown=False)
        new.open_tab(tab)

    if old is not new:
        global_log.info(f"Switching langservers: {old} --> {new}")
        tab.event_generate(
            "<<SetUnderlines>>", data=underlines.Underlines(id="diagnostics", underline_list=[])
        )

        if old is not None:
            old.forget_tab(tab)
        if new is not None:
            new.open_tab(tab)


def on_new_filetab(tab: tabs.FileTab) -> None:
    tab.settings.add_option("langserver", None, Optional[LangServerConfig])

    # TODO: some better way to pass events to the correct langsever?
    def request_completions(event: utils.EventWithData) -> str | None:
        for langserver in langservers.values():
            if tab in langserver.tabs_opened:
                langserver.request_completions(tab, event)
                return "break"
        return None

    def content_changed(event: utils.EventWithData) -> None:
        for langserver in langservers.values():
            if tab in langserver.tabs_opened:
                langserver.send_change_events(tab, event.data_class(textutils.Changes))

    def request_jump2def(event: object) -> str:
        for langserver in langservers.values():
            if tab in langserver.tabs_opened:
                langserver.request_jump_to_definition(tab)
        return "break"  # Do not insert newline

    def request_hover(event: utils.EventWithData) -> str | None:
        for langserver in langservers.values():
            if tab in langserver.tabs_opened:
                langserver.request_hover(tab, location=event.data_string)
                return "break"
        return None

    def on_destroy(event: object) -> None:
        for langserver in list(langservers.values()):
            if tab in langserver.tabs_opened:
                langserver.forget_tab(tab)

    utils.bind_with_data(tab.textwidget, "<<ContentChanged>>", content_changed, add=True)
    utils.bind_with_data(tab.textwidget, "<<JumpToDefinitionRequest>>", request_jump2def, add=True)
    utils.bind_with_data(tab.textwidget, "<<HoverRequest>>", request_hover, add=True)
    utils.bind_with_data(tab, "<<AutoCompletionRequest>>", request_completions, add=True)
    tab.bind("<Destroy>", on_destroy, add=True)

    tab.bind("<<TabSettingChanged:langserver>>", partial(switch_langservers, tab, False), add=True)
    tab.bind("<<PathChanged>>", partial(switch_langservers, tab, True), add=True)
    switch_langservers(tab, called_because_path_changed=False)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
