# langserver plugin
# TODO: sockets without specifying netcat as the command
# TODO: CompletionProvider
# TODO: error reporting in gui somehow

import collections
import errno
import itertools
import json
import logging
import os
import pathlib
import platform
import pprint
import queue
import re
import select
import shlex
import signal
import socket
import subprocess
import threading
import time
import typing
from urllib.request import pathname2url

try:
    import fcntl
except ImportError:
    # windows
    fcntl = None    # type: ignore

from porcupine import get_tab_manager, filetypes, tabs, utils
import sansio_lsp_client as lsp     # type: ignore


# 1024 bytes was way too small, and with this chunk size, it
# still sometimes takes two reads to get everything (that's fine)
CHUNK_SIZE = 64*1024


class SubprocessStdIO:

    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process

        if fcntl is None:
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

    # shitty windows code
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
    def read(self) -> typing.Optional[bytes]:
        if fcntl is None:
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
    if platform.system() == 'Windows':
        # i tried socket.socket().recv(1024) on windows and this is what i got
        return (error.winerror == 10057)    # type: ignore
    else:
        return (error.errno == errno.ENOTCONN)


class LocalhostSocketIO:

    def __init__(self, port: int, log: logging.Logger) -> None:
        self._sock = socket.socket()

        # This queue solves two problems:
        #   - I don't feel like learning to do non-blocking send right now.
        #   - It must be possible to .write() before the socket is connected.
        #     The written bytes get sent when the socket connects.
        self._send_queue: queue.Queue[typing.Optional[bytes]] = queue.Queue()

        self._worker_thread = threading.Thread(
            target=self._send_queue_to_socket, args=[port, log], daemon=True)
        self._worker_thread.start()

    def _send_queue_to_socket(self, port: int, log: logging.Logger) -> None:
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
    def read(self) -> typing.Optional[bytes]:
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


# TODO: add a configuration option for this, and make this a part of porcupine
#       rather than something that every plugin has to implement
# TODO: editorconfig support
_PROJECT_ROOT_THINGS = ['editorconfig', '.git'] + [
    readme + extension
    for readme in ['README', 'readme', 'Readme', 'ReadMe']
    for extension in ['', '.txt', '.md']
]


def find_project_root(project_file_path: pathlib.Path) -> pathlib.Path:
    assert project_file_path.is_absolute()

    path = project_file_path
    while True:
        parent = path.parent
        if path == parent:      # shitty default
            return project_file_path.parent
        path = parent

        if any((path / thing).exists() for thing in _PROJECT_ROOT_THINGS):
            return path


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
        #
        # without this check, this wouldn't show arguments of foo on right side
        if item.documentation.startswith(item.label.strip()):
            return item.documentation
        else:
            return item.label.strip() + '\n\n' + item.documentation

    return item.label


def exit_code_string(exit_code: int) -> str:
    if exit_code >= 0:
        return "exited with code %d" % exit_code

    signal_number = abs(exit_code)
    result = "was killed by signal %d" % signal_number

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


class LangServerId(typing.NamedTuple):
    command: str
    port: typing.Optional[int]
    project_root: pathlib.Path


class LangServer:

    def __init__(
            self,
            process: subprocess.Popen,
            the_id: LangServerId,
            log: logging.Logger) -> None:
        self._process = process
        self._id = the_id
        self._lsp_client = lsp.Client(
            trace='verbose', root_uri=the_id.project_root.as_uri())

        # TODO: don't use typing.Any
        self._completion_infos: typing.Dict[
            int, typing.Dict[str, typing.Any]] = {}

        self._version_counter = itertools.count()
        self._log = log
        self.tabs_opened: typing.List[tabs.FileTab] = []
        self._is_shutting_down_cleanly = False

        self._io: typing.Union[SubprocessStdIO, LocalhostSocketIO]
        if the_id.port is None:
            self._io = SubprocessStdIO(process)
        else:
            self._io = LocalhostSocketIO(the_id.port, log)

    def _is_in_langservers(self) -> bool:
        # This returns False if a langserver died and another one with the same
        # command was launched.
        return (langservers.get(self._id, None) is self)

    def _get_removed_from_langservers(self) -> None:
        # this is called more than necessary to make sure we don't end up with
        # funny issues caused by unusable langservers
        if self._is_in_langservers():
            self._log.debug("getting removed from langservers")
            del langservers[self._id]

    # returns whether this should be called again later
    def _ensure_langserver_process_quits_soon(self) -> None:
        exit_code = self._process.poll()
        if exit_code is None:
            if self._lsp_client.state == lsp.ClientState.EXITED:
                # process still running, but will exit soon. Let's make sure
                # to log that when it happens so that if it doesn't exit for
                # whatever reason, then that will be visible in logs.
                self._log.debug("langserver process should stop soon")
                get_tab_manager().after(
                    500, self._ensure_langserver_process_quits_soon)
                return

            # langserver doesn't want to exit, let's kill it
            what_closed = (
                'stdout' if self._id.port is None
                else 'socket connection'
            )
            self._log.warn(
                f"killing langserver process {self._process.pid} "
                f"because {what_closed} has closed for some reason")

            self._process.kill()
            exit_code = self._process.wait()

        if self._is_shutting_down_cleanly:
            self._log.info(
                "langserver process terminated, %s",
                exit_code_string(exit_code))
        else:
            self._log.error(
                "langserver process terminated unexpectedly, %s",
                exit_code_string(exit_code))

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
        self._log.debug("got %d bytes of data", len(received_bytes))

        try:
            lsp_events = self._lsp_client.recv(received_bytes)
        except Exception:
            self._log.exception("error while receiving lsp events")
            lsp_events = []

        for lsp_event in lsp_events:
            try:
                self._handle_lsp_event(lsp_event)
            except Exception:
                self._log.exception("error while handling langserver event")

        return True

    def _send_tab_opened_message(self, tab: tabs.FileTab) -> None:
        self._lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=tab.path.as_uri(),
                languageId=tab.filetype.langserver_language_id,
                text=tab.textwidget.get('1.0', 'end - 1 char'),
                version=0,
            )
        )

    def _handle_lsp_event(self, lsp_event: lsp.Event) -> None:
        if isinstance(lsp_event, lsp.Initialized):
            self._log.info("langserver initialized, capabilities:\n%s",
                           pprint.pformat(lsp_event.capabilities))

            for tab in self.tabs_opened:
                self._send_tab_opened_message(tab)

        elif isinstance(lsp_event, lsp.Shutdown):
            self._log.debug("langserver sent Shutdown event")
            self._lsp_client.exit()
            self._get_removed_from_langservers()

        elif isinstance(lsp_event, lsp.Completion):
            info_dict = self._completion_infos.pop(lsp_event.message_id)
            tab = info_dict.pop('tab')

            # this is "open to interpretation", as the lsp spec says
            # TODO: use textEdit when available (need to find langserver that
            #       gives completions with textEdit for that to work)
            before_cursor = tab.textwidget.get(
                '%s linestart' % info_dict['cursor_pos'],
                info_dict['cursor_pos'])
            match = re.fullmatch(r'.*?(\w*)', before_cursor)
            assert match is not None
            prefix_len = len(match.group(1))

            info_dict['completions'] = [
                {
                    'display_text': item.label,
                    'replace_start': tab.textwidget.index(
                        f"{info_dict['cursor_pos']} - {prefix_len} chars"),
                    'replace_end': info_dict['cursor_pos'],
                    'replace_text': item.insertText or item.label,
                    'filter_text': (item.filterText
                                    or item.insertText
                                    or item.label)[prefix_len:],
                    'documentation': get_completion_item_doc(item),
                }
                for item in sorted(
                    lsp_event.completion_list.items,
                    key=(lambda item: item.sortText or item.label),
                )
            ]
            tab.event_generate(
                '<<AutoCompletionResponse>>', data=json.dumps(info_dict))

        elif isinstance(lsp_event, lsp.PublishDiagnostics):
            pass        # TODO

        elif isinstance(lsp_event, lsp.LogMessage):
            loglevel_dict = {
                lsp.MessageType.LOG: logging.DEBUG,
                lsp.MessageType.INFO: logging.INFO,
                lsp.MessageType.WARNING: logging.WARNING,
                lsp.MessageType.ERROR: logging.ERROR,
            }
            self._log.log(loglevel_dict[lsp_event.type],
                          "message from langserver: %s", lsp_event.message)

        else:
            raise NotImplementedError(lsp_event)

    def run_stuff(self) -> None:
        if self._run_stuff_once():
            get_tab_manager().after(50, self.run_stuff)

    def open_tab(self, tab: tabs.FileTab) -> None:
        self._log.debug("tab opened")
        self.tabs_opened.append(tab)
        if self._lsp_client.state == lsp.ClientState.NORMAL:
            self._send_tab_opened_message(tab)

    def close_tab(self, tab: tabs.FileTab) -> None:
        if not self._is_in_langservers():
            self._log.debug(
                "a tab was closed, but langserver process is no longer "
                "running (maybe it crashed?)")
            return

        self._log.debug("tab closed")
        self.tabs_opened.remove(tab)
        if not self.tabs_opened:
            self._log.info("no more open tabs, shutting down")
            self._is_shutting_down_cleanly = True
            self._get_removed_from_langservers()

            if self._lsp_client.state == lsp.ClientState.NORMAL:
                self._lsp_client.shutdown()
            else:
                # it was never fully started
                self._process.kill()

    def request_completions(self, event: lsp.Event) -> None:
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            self._log.warning(
                "autocompletions requested but langserver state == %r",
                self._lsp_client.state)
            return

        tab = event.widget
        info_dict = event.data_json()

        lsp_id = self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=tab.path.as_uri()),
                position=_position_tk2lsp(info_dict['cursor_pos']),
            ),
            context=lsp.CompletionContext(
                # FIXME: this isn't always the case, porcupine can also trigger
                #        it automagically
                triggerKind=lsp.CompletionTriggerKind.INVOKED,
            ),
        )

        assert lsp_id not in self._completion_infos
        self._completion_infos[lsp_id] = info_dict
        self._completion_infos[lsp_id]['tab'] = tab

    def send_change_events(self, event: lsp.Event) -> None:
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            # The langserver will receive the actual content of the file once
            # it starts.
            self._log.debug(
                "not sending change events because langserver state == %r",
                self._lsp_client.state)
            return

        tab = event.widget.master
        assert isinstance(tab, tabs.FileTab)
        self._lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=tab.path.as_uri(),
                version=next(self._version_counter),
            ),
            content_changes=[
                lsp.TextDocumentContentChangeEvent(
                    range=lsp.Range(
                        start=_position_tk2lsp(info['start']),
                        end=_position_tk2lsp(info['end']),
                    ),
                    text=info['new_text'],
                )
                for info in event.data_json()
            ],
        )


langservers: typing.Dict[LangServerId, LangServer] = {}


# I was going to add code that checks if two langservers use the same port
# number, but it's unnecessary: if a langserver tries to use a port number that
# is already being used, then it should exit with an error message.


def get_lang_server(
        filetype: filetypes.FileType,
        project_root: pathlib.Path) -> typing.Optional[LangServer]:
    if not (filetype.langserver_command and filetype.langserver_language_id):
        logging.getLogger(__name__).info(
            "langserver not configured for filetype " + filetype.name)
        return None

    the_id = LangServerId(
        filetype.langserver_command, filetype.langserver_port, project_root)

    try:
        return langservers[the_id]
    except KeyError:
        pass

    log = logging.getLogger(
        # this is lol
        __name__ + '.' + re.sub(
            r'[^A-Za-z0-9]', '_',
            filetype.langserver_command + ' ' + str(project_root)))

    # avoid shell=True on non-windows to get process.pid to do the right thing
    #
    # with shell=True it's the pid of the shell, not the pid of the program
    #
    # on windows, there is no shell and it's all about whether to quote or not
    command: typing.Union[str, typing.List[str]]
    if platform.system() == 'Windows':
        shell = True
        command = filetype.langserver_command
    else:
        shell = False
        command = shlex.split(filetype.langserver_command)

    try:
        # TODO: read and log stderr
        process = subprocess.Popen(
            command, shell=shell,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError):
        log.exception(
            "cannot start langserver process with command '%s'",
            filetype.langserver_command)
        return None

    log.info("Langserver process started with command '%s', PID %d, "
             "for project root '%s'",
             filetype.langserver_command, process.pid, project_root)

    langserver = LangServer(process, the_id, log)
    langserver.run_stuff()
    langservers[the_id] = langserver
    return langserver


def on_new_tab(event: utils.EventWithData) -> None:
    tab: tabs.Tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        if tab.path is None or tab.filetype is None:
            # TODO
            return

        langserver = get_lang_server(tab.filetype, find_project_root(tab.path))
        if langserver is None:
            return

        utils.bind_with_data(tab, '<<AutoCompletionRequest>>',
                             langserver.request_completions, add=True)
        utils.bind_with_data(tab.textwidget, '<<ContentChanged>>',
                             langserver.send_change_events, add=True)
        tab.bind('<Destroy>', lambda event: langserver.close_tab(tab),
                 add=True)

        langserver.open_tab(tab)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
