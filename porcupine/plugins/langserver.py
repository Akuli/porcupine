"""Langserver support for autocompletions."""
# TODO: CompletionProvider
# TODO: error reporting in gui somehow
from __future__ import annotations

import dataclasses
import errno
import itertools
import logging
import os
import pathlib
import pprint
import queue
import re
import select
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
from functools import partial
from typing import IO, Dict, List, NamedTuple, Optional, Tuple, Union

if sys.platform != 'win32':
    import fcntl

import sansio_lsp_client as lsp

from porcupine import get_tab_manager, tabs, textwidget, utils
from porcupine.plugins import autocomplete, underlines

global_log = logging.getLogger(__name__)


# 1024 bytes was way too small, and with this chunk size, it
# still sometimes takes two reads to get everything (that's fine)
CHUNK_SIZE = 64*1024


class SubprocessStdIO:

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process

        if sys.platform == 'win32':
            self._read_queue: queue.Queue[bytes] = queue.Queue()
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._stdout_to_read_queue, daemon=True)
            self._worker_thread.start()
        else:
            # this works because we don't use .readline()
            # https://stackoverflow.com/a/1810703
            assert process.stdout is not None
            fileno = process.stdout.fileno()
            old_flags = fcntl.fcntl(fileno, fcntl.F_GETFL)
            new_flags = old_flags | os.O_NONBLOCK
            fcntl.fcntl(fileno, fcntl.F_SETFL, new_flags)

    if sys.platform == 'win32':
        def _stdout_to_read_queue(self) -> None:
            while True:
                # for whatever reason, nothing works unless i go ONE BYTE at a
                # time.... this is a piece of shit
                assert self._process.stdout is not None
                one_fucking_byte = self._process.stdout.read(1)
                if not one_fucking_byte:
                    break
                self._read_queue.put(one_fucking_byte)

    # Return values:
    #   - nonempty bytes object: data was read
    #   - empty bytes object: process exited
    #   - None: no data to read
    def read(self) -> Optional[bytes]:
        if sys.platform == 'win32':
            # shitty windows code
            buf = bytearray()
            while True:
                try:
                    buf += self._read_queue.get(block=False)
                except queue.Empty:
                    break

            if self._worker_thread.is_alive() and not buf:
                return None
            return bytes(buf)

        else:
            assert self._process.stdout is not None
            return self._process.stdout.read(CHUNK_SIZE)

    def write(self, bytez: bytes) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(bytez)
        self._process.stdin.flush()


def error_says_socket_not_connected(error: OSError) -> bool:
    if sys.platform == 'win32':
        return (error.winerror == 10057)
    else:
        return (error.errno == errno.ENOTCONN)


class LocalhostSocketIO:

    def __init__(self, port: int, log: logging.LoggerAdapter) -> None:
        self._sock = socket.socket()

        # This queue solves two problems:
        #   - I don't feel like learning to do non-blocking send right now.
        #   - It must be possible to .write() before the socket is connected.
        #     The written bytes get sent when the socket connects.
        self._send_queue: queue.Queue[Optional[bytes]] = queue.Queue()

        self._worker_thread = threading.Thread(
            target=self._send_queue_to_socket, args=[port, log], daemon=True)
        self._worker_thread.start()

    def _send_queue_to_socket(self, port: int, log: logging.LoggerAdapter) -> None:
        while True:
            try:
                self._sock.connect(('localhost', port))
                log.info(f"connected to localhost:{port}")
                break
            except ConnectionRefusedError:
                log.info(
                    f"connecting to localhost:{port} failed, retrying soon")
                time.sleep(0.5)

        while True:
            bytez = self._send_queue.get()
            if bytez is None:
                break
            self._sock.sendall(bytez)

    def write(self, bytez: bytes) -> None:
        self._send_queue.put(bytez)

    # Return values:
    #   - nonempty bytes object: data was received
    #   - empty bytes object: socket closed
    #   - None: no data to receive
    def read(self) -> Optional[bytes]:
        # figure out if we can read from the socket without blocking
        # 0 is timeout, i.e. return immediately
        #
        # TODO: pass the correct non-block flag to recv instead?
        #       does that work on windows?
        can_read, can_write, error = select.select([self._sock], [], [], 0)
        if self._sock not in can_read:
            return None

        try:
            result = self._sock.recv(CHUNK_SIZE)
        except OSError as e:
            if error_says_socket_not_connected(e):
                return None
            raise e

        if not result:
            assert result == b''
            # stop worker thread
            if self._worker_thread.is_alive():
                self._send_queue.put(None)
        return result


def completion_item_doc_contains_label(doc: str, label: str) -> bool:
    # this used to be doc.startswith(label), but see issue #67
    label = label.strip()
    if '(' in label:
        prefix = label.strip().split('(')[0] + '('
    else:
        prefix = label.strip()
    return doc.startswith(prefix)


def get_completion_item_doc(item: lsp.CompletionItem) -> str:
    if item.documentation:
        # try this with clangd
        #
        #    // comment
        #    void foo(int x, char c) { }
        #
        #    int main(void)
        #    {
        #        fo<Tab>
        #    }
        if completion_item_doc_contains_label(item.documentation, item.label):
            result = item.documentation
        else:
            result = item.label.strip() + '\n\n' + item.documentation
    else:
        result = item.label

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


def _position_tk2lsp(tk_position: str) -> lsp.Position:
    # this can't use tab.textwidget.index, because it needs to handle text
    # locations that don't exist anymore when text has been deleted
    line, column = map(int, tk_position.split('.'))

    # lsp line numbering starts at 0
    # tk line numbering starts at 1
    # both column numberings start at 0
    return lsp.Position(line=line-1, character=column)


def _position_lsp2tk(lsp_position: lsp.Position) -> str:
    return f'{lsp_position.line + 1}.{lsp_position.character}'


def _get_diagnostic_string(diagnostic: lsp.Diagnostic) -> str:
    if diagnostic.source is None:
        assert diagnostic.message is not None  # TODO
        return diagnostic.message
    return f'{diagnostic.source}: {diagnostic.message}'


@dataclasses.dataclass
class LangServerConfig:
    command: str
    language_id: str
    port: Optional[int] = None


# FIXME: two langservers with same command, same port, different project_root
class LangServerId(NamedTuple):
    command: str
    port: Optional[int]
    project_root: pathlib.Path


class LangServer:

    def __init__(
            self,
            process: subprocess.Popen[bytes],
            the_id: LangServerId,
            log: logging.LoggerAdapter) -> None:
        self._process = process
        self._id = the_id
        self._lsp_client = lsp.Client(
            trace='verbose', root_uri=the_id.project_root.as_uri())

        self._lsp_id_to_tab_and_request: Dict[lsp.Id, Tuple[tabs.FileTab, autocomplete.Request]] = {}

        self._version_counter = itertools.count()
        self.log = log
        self.tabs_opened: Dict[tabs.FileTab, List[utils.TemporaryBind]] = {}
        self._is_shutting_down_cleanly = False

        self._io: Union[SubprocessStdIO, LocalhostSocketIO]
        if the_id.port is None:
            self._io = SubprocessStdIO(process)
        else:
            self._io = LocalhostSocketIO(the_id.port, log)

    def __repr__(self) -> str:
        return (f"<{type(self).__name__}: "
                f"PID {self._process.pid}, "
                f"{self._id}, "
                f"{len(self.tabs_opened)} tabs opened>")

    def _is_in_langservers(self) -> bool:
        # This returns False if a langserver died and another one with the same
        # id was launched.
        return (langservers.get(self._id, None) is self)

    def _get_removed_from_langservers(self) -> None:
        # this is called more than necessary to make sure we don't end up with
        # funny issues caused by unusable langservers
        if self._is_in_langservers():
            self.log.debug("getting removed from langservers")
            del langservers[self._id]

    # returns whether this should be called again later
    def _ensure_langserver_process_quits_soon(self) -> None:
        exit_code = self._process.poll()
        if exit_code is None:
            if self._lsp_client.state == lsp.ClientState.EXITED:
                # process still running, but will exit soon. Let's make sure
                # to log that when it happens so that if it doesn't exit for
                # whatever reason, then that will be visible in logs.
                self.log.debug("langserver process should stop soon")
                get_tab_manager().after(
                    500, self._ensure_langserver_process_quits_soon)
                return

            # langserver doesn't want to exit, let's kill it
            what_closed = (
                'stdout' if self._id.port is None
                else 'socket connection'
            )
            self.log.warning(
                f"killing langserver process {self._process.pid} "
                f"because {what_closed} has closed for some reason")

            self._process.kill()
            exit_code = self._process.wait()

        if self._is_shutting_down_cleanly:
            self.log.info(f"langserver process terminated, {exit_code_string(exit_code)}")
        else:
            self.log.error(f"langserver process terminated unexpectedly, {exit_code_string(exit_code)}")

        self._get_removed_from_langservers()

    # returns whether this should be ran again
    def _run_stuff_once(self) -> bool:
        self._io.write(self._lsp_client.send())
        received_bytes = self._io.read()

        # yes, None and b'' have a different meaning here
        if received_bytes is None:
            # no data received
            return True
        elif received_bytes == b'':
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
            lsp_events = self._lsp_client.recv(received_bytes)
        except Exception:
            self.log.exception("error while receiving lsp events")
            lsp_events = []

        for lsp_event in lsp_events:
            try:
                self._handle_lsp_event(lsp_event)
            except Exception:
                self.log.exception("error while handling langserver event")

        return True

    def _send_tab_opened_message(self, tab: tabs.FileTab) -> None:
        config = tab.settings.get('langserver', Optional[LangServerConfig])
        assert isinstance(config, LangServerConfig)
        assert tab.path is not None

        self._lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=tab.path.as_uri(),
                languageId=config.language_id,
                text=tab.textwidget.get('1.0', 'end - 1 char'),
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
            self.log.log(loglevel_dict[lsp_event.type],
                         f"message from langserver: {lsp_event.message}")
            return

        # rest of these need the langserver to be active
        if not self._is_in_langservers():
            self.log.warning(f"ignoring event because langserver is shutting down: {lsp_event}")
            return

        if isinstance(lsp_event, lsp.Initialized):
            self.log.info("langserver initialized, capabilities:\n" + pprint.pformat(lsp_event.capabilities))

            for tab in self.tabs_opened.keys():
                self._send_tab_opened_message(tab)
            return

        if isinstance(lsp_event, lsp.Completion):
            tab, req = self._lsp_id_to_tab_and_request.pop(lsp_event.message_id)
            if tab not in self.tabs_opened:
                # I wouldn't be surprised if some langserver sent completions to closed tabs
                self.log.debug(f"Completion sent to closed tab: {lsp_event}")
                return

            # this is "open to interpretation", as the lsp spec says
            # TODO: use textEdit when available (need to find langserver that
            #       gives completions with textEdit for that to work)
            before_cursor = tab.textwidget.get(
                f'{req.cursor_pos} linestart', req.cursor_pos)
            match = re.fullmatch(r'.*?(\w*)', before_cursor)
            assert match is not None
            prefix_len = len(match.group(1))

            assert lsp_event.completion_list is not None
            if isinstance(lsp_event.completion_list, list):
                completions = lsp_event.completion_list
            else:
                completions = lsp_event.completion_list.items

            tab.event_generate(
                '<<AutoCompletionResponse>>',
                data=autocomplete.Response(
                    id=req.id,
                    completions=[
                        autocomplete.Completion(
                            display_text=item.label,
                            replace_start=tab.textwidget.index(
                                f'{req.cursor_pos} - {prefix_len} chars'),
                            replace_end=req.cursor_pos,
                            replace_text=item.insertText or item.label,
                            # TODO: is slicing necessary here?
                            filter_text=(item.filterText
                                         or item.insertText
                                         or item.label)[prefix_len:],
                            documentation=get_completion_item_doc(item),
                        ) for item in sorted(
                            completions,
                            key=(lambda item: item.sortText or item.label),
                        )
                    ]
                )
            )
            return

        if isinstance(lsp_event, lsp.PublishDiagnostics):
            matching_tabs = [
                tab for tab in self.tabs_opened.keys()
                if tab.path is not None and tab.path.as_uri() == lsp_event.uri
            ]
            if not matching_tabs:
                # Some langservers send diagnostics to closed tabs
                self.log.debug(f"PublishDiagnostics sent to closed tab: {lsp_event}")
                return
            [tab] = matching_tabs

            tab.event_generate('<<SetUnderlines>>', data=underlines.Underlines(
                id='langserver_diagnostics',
                underline_list=[
                    underlines.Underline(
                        start=_position_lsp2tk(diagnostic.range.start),
                        end=_position_lsp2tk(diagnostic.range.end),
                        message=_get_diagnostic_string(diagnostic),
                        # TODO: there are plenty of other severities than ERROR and WARNING
                        color=('red' if diagnostic.severity == lsp.DiagnosticSeverity.ERROR else 'orange'),
                    )
                    for diagnostic in sorted(
                        lsp_event.diagnostics,
                        # error red underlines should be shown over orange warning underlines
                        key=(lambda diagn: diagn.severity),
                        reverse=True,
                    )
                ],
            ))
            return

        raise NotImplementedError(lsp_event)

    def run_stuff(self) -> None:
        if self._run_stuff_once():
            get_tab_manager().after(50, self.run_stuff)

    def open_tab(self, tab: tabs.FileTab) -> None:
        assert tab not in self.tabs_opened
        self.tabs_opened[tab] = [
            utils.TemporaryBind(tab, '<<AutoCompletionRequest>>', self.request_completions),
            utils.TemporaryBind(tab.textwidget, '<<ContentChanged>>', partial(self.send_change_events, tab)),
            utils.TemporaryBind(tab, '<Destroy>', (lambda event: self.forget_tab(tab))),
        ]

        self.log.debug("tab opened")
        if self._lsp_client.state == lsp.ClientState.NORMAL:
            self._send_tab_opened_message(tab)

    def forget_tab(self, tab: tabs.FileTab, *, may_shutdown: bool = True) -> None:
        if not self._is_in_langservers():
            self.log.debug(
                "a tab was closed, but langserver process is no longer "
                "running (maybe it crashed?)")
            return

        self.log.debug("tab closed")
        for binding in self.tabs_opened.pop(tab):
            binding.unbind()

        if may_shutdown and not self.tabs_opened:
            self.log.info("no more open tabs, shutting down")
            self._is_shutting_down_cleanly = True
            self._get_removed_from_langservers()

            if self._lsp_client.state == lsp.ClientState.NORMAL:
                self._lsp_client.shutdown()
            else:
                # it was never fully started
                self._process.kill()

    def request_completions(self, event: utils.EventWithData) -> None:
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            self.log.warning(f"autocompletions requested but langserver state == {self._lsp_client.state!r}")
            return

        tab = event.widget
        assert isinstance(tab, tabs.FileTab) and tab.path is not None
        request = event.data_class(autocomplete.Request)

        lsp_id = self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=tab.path.as_uri()),
                position=_position_tk2lsp(request.cursor_pos),
            ),
            context=lsp.CompletionContext(
                # FIXME: this isn't always the case, porcupine can also trigger
                #        it automagically
                triggerKind=lsp.CompletionTriggerKind.INVOKED,
            ),
        )

        assert lsp_id not in self._lsp_id_to_tab_and_request
        self._lsp_id_to_tab_and_request[lsp_id] = (tab, request)

    def send_change_events(self, tab: tabs.FileTab, event: utils.EventWithData) -> None:
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            # The langserver will receive the actual content of the file once
            # it starts.
            self.log.debug(f"not sending change events because langserver state == {self._lsp_client.state!r}")
            return

        assert tab.path is not None
        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=tab.path.as_uri(),
                version=next(self._version_counter),
            ),
            content_changes=[
                lsp.TextDocumentContentChangeEvent(
                    range=lsp.Range(
                        start=_position_tk2lsp(change.start),
                        end=_position_tk2lsp(change.end),
                    ),
                    text=change.new_text,
                )
                for change in event.data_class(textwidget.Changes).change_list
            ],
        )


langservers: Dict[LangServerId, LangServer] = {}


# I was going to add code that checks if two langservers use the same port
# number, but it's unnecessary: if a langserver tries to use a port number that
# is already being used, then it should exit with an error message.


def stream_to_log(stream: IO[bytes], log: logging.LoggerAdapter) -> None:
    for line_bytes in stream:
        line = line_bytes.rstrip(b'\r\n').decode('utf-8', errors='replace')
        log.info(f"langserver logged: {line}")


def get_lang_server(tab: tabs.FileTab) -> Optional[LangServer]:
    if tab.path is None:
        return None

    config = tab.settings.get('langserver', Optional[LangServerConfig])
    if config is None:
        return None
    assert isinstance(config, LangServerConfig)

    project_root = utils.find_project_root(tab.path)
    the_id = LangServerId(config.command, config.port, project_root)
    try:
        return langservers[the_id]
    except KeyError:
        pass

    # avoid shell=True on non-windows to get process.pid to do the right thing
    #
    # with shell=True it's the pid of the shell, not the pid of the program
    #
    # on windows, there is no shell and it's all about whether to quote or not
    actual_command: Union[str, List[str]]
    if sys.platform == 'win32':
        shell = True
        actual_command = config.command
    else:
        shell = False
        actual_command = shlex.split(config.command)

    try:
        if the_id.port is None:
            # langserver writes log messages to stderr
            process = subprocess.Popen(
                actual_command, shell=shell,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            # most langservers log to stderr, but also watch stdout
            process = subprocess.Popen(
                actual_command, shell=shell,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError):
        global_log.exception(f"failed to start langserver with command {config.command!r}")
        return None

    log = logging.LoggerAdapter(global_log, {})
    log.process = lambda msg, kwargs: (f'(PID={process.pid}) {msg}', kwargs)  # type: ignore
    log.info(f"Langserver process started with command '{config.command}', project root '{project_root}'")

    logging_stream = process.stderr if the_id.port is None else process.stdout
    assert logging_stream is not None
    threading.Thread(target=stream_to_log, args=[logging_stream, log], daemon=True).start()

    langserver = LangServer(process, the_id, log)
    langserver.run_stuff()
    langservers[the_id] = langserver
    return langserver


# Switch the tab to another langserver, starting one if needed
def switch_langservers(tab: tabs.FileTab, called_because_path_changed: bool, junk: object = None) -> None:
    old = next((
        langserver
        for langserver in langservers.values()
        if tab in langserver.tabs_opened
    ), None)
    new = get_lang_server(tab)

    if old is not None and new is not None and old is new and called_because_path_changed:
        old.log.info("Path changed, closing and reopening the tab")
        old.forget_tab(tab, may_shutdown=False)
        new.open_tab(tab)

    if old is not new:
        global_log.info(f"Switching langservers: {old} --> {new}")
        if old is not None:
            old.forget_tab(tab)
        if new is not None:
            new.open_tab(tab)


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        tab.settings.add_option('langserver', None, Optional[LangServerConfig])

        tab.bind('<<TabSettingChanged:langserver>>', partial(switch_langservers, tab, False), add=True)
        tab.bind('<<PathChanged>>', partial(switch_langservers, tab, True), add=True)
        switch_langservers(tab, False)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
