# langserver plugin

import shlex
import itertools
import json
import logging
import os
import platform
import pprint
import queue as queue_module
import re
import signal
import subprocess
import threading
from urllib.request import pathname2url

try:
    import fcntl
except ImportError:
    # windows
    fcntl = None

from porcupine import get_tab_manager, tabs, utils
import sansio_lsp_client as lsp


def get_nonblocking_reader(file):
    if fcntl is not None:
        # this works because we don't use .readline()
        # https://stackoverflow.com/a/1810703
        old_flags = fcntl.fcntl(file.fileno(), fcntl.F_GETFL)
        new_flags = old_flags | os.O_NONBLOCK
        fcntl.fcntl(file.fileno(), fcntl.F_SETFL, new_flags)

        # 1024 bytes was way too small, and with this chunk size, it
        # still sometimes takes two reads to get everything
        return lambda: file.read(64*1024)

    # rest of this is windows only code, why can't windows just have a nice way
    # to make stuff not block?

    queue = queue_module.Queue()
    running = True

    def put_to_queue():
        while True:
            # for whatever reason, nothing works unless i go ONE BYTE at a
            # time.... this is a piece of shit
            one_fucking_byte = file.read(1)
            if not one_fucking_byte:
                nonlocal running
                running = False
                break
            queue.put(one_fucking_byte)

    def get_from_queue():
        buf = bytearray()
        while True:
            try:
                buf += queue.get(block=False)
            except queue_module.Empty:
                break

        if buf:
            return bytes(buf)
        return None if running else b''

    threading.Thread(target=put_to_queue, daemon=True).start()
    return get_from_queue


def get_uri(tab):
    assert tab.path is not None
    return 'file://' + pathname2url(os.path.abspath(tab.path))


def get_markup_content(string_or_lsp_markupcontent) -> str:
    if isinstance(string_or_lsp_markupcontent, lsp.MarkupContent):
        return string_or_lsp_markupcontent.value
    return str(string_or_lsp_markupcontent)


def exit_code_string(exit_code):
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


# keys are running commands because the same langserver command might be useful
# for multiple langservers
langservers = {}


class LangServer:

    def __init__(self, process, command, log):
        self._process = process
        self._command = command
        self._lsp_client = lsp.Client(trace='verbose')
        self._completion_infos = {}
        self._version_counter = itertools.count()
        self._log = log
        self.tabs_opened = []      # list of tabs
        self._nonblocking_stdout_read = get_nonblocking_reader(
            self._process.stdout)
        self._is_shutting_down_cleanly = False

    def _is_in_langservers(self):
        # This returns False if a langserver died and another one with the same
        # command was launched.
        return (langservers.get(self._command, None) is self)

    def _get_removed_from_langservers(self):
        # this is called more than necessary to make sure we don't end up with
        # funny issues caused by unusable langservers
        if self._is_in_langservers():
            self._log.debug("getting removed from langservers")
            del langservers[self._command]

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

        received_bytes = self._nonblocking_stdout_read()

        # yes, None and b'' have a different meaning here
        if received_bytes is None:
            # no data received
            return True
        elif received_bytes == b'':
            # it has died already, so .wait() doesn't actually wait for
            # anything to happen. It's needed for getting return code.
            exit_code = self._process.wait()

            if self._is_shutting_down_cleanly:
                self._log.info(
                    "langserver process terminated, %s",
                    exit_code_string(exit_code))
            else:
                self._log.error(
                    "langserver process terminated unexpectedly, %s",
                    exit_code_string(exit_code))
                # TODO: restart it?

            self._get_removed_from_langservers()
            return False

        assert received_bytes
        self._log.debug("got %d bytes of data", len(received_bytes))

        try:
            lsp_events = self._lsp_client.recv(received_bytes)
        except lsp.IncompleteResponseError:
            return True
        except Exception:
            self._log.exception("error while receiving lsp events")
            lsp_events = []

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
                languageId=tab.filetype.langserver_language_id,
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
            self._log.debug("langserver sent Shutdown event")
            self._lsp_client.exit()
            self._get_removed_from_langservers()

        elif isinstance(lsp_event, lsp.Completion):
            info_dict = self._completion_infos.pop(lsp_event.message_id)
            tab = info_dict.pop('tab')

            # this is "open to interpretation", as the lsp spec says
            # TODO: use textEdit when available (requires some refactoring)
            before_cursor = tab.textwidget.get(
                '%s linestart' % info_dict['cursor_pos'],
                info_dict['cursor_pos'])
            prefix_len = len(re.fullmatch(r'.*?(\w*)', before_cursor).group(1))

            info_dict['completions'] = [
                {
                    'display_text': item.label,
                    'suffix': (item.insertText or item.label)[prefix_len:],
                    'filter_text': (item.filterText
                                    or item.insertText
                                    or item.label)[prefix_len:],
                    'documentation': item.documentation or item.label,
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

        else:
            raise NotImplementedError(lsp_event)

    def run_stuff(self):
        if self._run_stuff_once():
            get_tab_manager().after(50, self.run_stuff)

    def open_tab(self, tab):
        self._log.debug("tab opened")
        self.tabs_opened.append(tab)
        if self._lsp_client.state == lsp.ClientState.NORMAL:
            self._send_tab_opened_message(tab)

    def close_tab(self, tab):
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

    def request_completions(self, event):
        if self._lsp_client.state != lsp.ClientState.NORMAL:
            self._log.warning(
                "autocompletions requested but langserver state == %r",
                self._lsp_client.state)
            return

        tab = event.widget
        info_dict = event.data_json()

        lsp_id = self._lsp_client.completions(
            text_document_position=lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=get_uri(tab)),
                position=self._position_tk2lsp(
                    info_dict['cursor_pos'], next_column=True
                ),
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

    def send_change_events(self, event):
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


def get_lang_server(filetype):
    if filetype is None:
        return None

    if not (filetype.langserver_command and filetype.langserver_language_id):
        logging.getLogger(__name__).info(
            "langserver not configured for filetype " + filetype.name)
        return None

    try:
        return langservers[filetype.langserver_command]
    except KeyError:
        pass

    log = logging.getLogger(
        __name__ + '.' +
        re.sub(r'[^A-Za-z0-9]', '_', filetype.langserver_command))     # lol

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
        process, filetype.langserver_command, log)
    langserver.run_stuff()
    langservers[filetype.langserver_command] = langserver
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
        tab.bind('<Destroy>', lambda event: langserver.close_tab(tab),
                 add=True)

        langserver.open_tab(tab)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
