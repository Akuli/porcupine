import sys
import subprocess
import porcupine
import queue

import kieli

from .utils import (
    tab_uri,
    tab_text,
    tab_position,
    lsp_pos_to_tk_pos,
    tk_pos_to_lsp_pos,
    find_overlap_start,
)


class Client:
    SERVER_COMMANDS = {"Python": [sys.executable, "-m", "pyls"]}

    def __init__(self, tab):
        self.tab = tab

        self._version = 0

        self._completions_queue = queue.Queue()

        stdin, stdout = self._start_process()
        self._client = kieli.LSPClient(stdin, stdout)
        self._client.response_handler("initialize")(self._initialize_response)
        # self._client.notification_handler("textDocument/publishDiagnostics")(
        #     self._publish_diagnostics
        # )

    def _publish_diagnostics(self, notification):
        print("Diagnostics:", notification.params, sep="\n")

    def _completions_response(self, _request, response):
        print("Completions response:", response)

        assert not response.result["isIncomplete"]
        self._completions_queue.put(response.result["items"])

    def _initialize_response(self, _request, _response):
        self._client.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": tab_uri(self._tab),
                    "languageId": self._tab.filetype.name.lower(),
                    "version": self._version,
                    "text": tab_text(self._tab),
                }
            },
        )

        self._tab.completer = lambda *_: self.get_completions()

        # TODO(PurpleMyst): Initialization takes forever. While a printout
        # is fine for development, we probably should add a little spinny
        # thing somewhere.
        print(
            "Language server for {!r} is initialized.".format(self._tab.path)
        )

        self._tab.bind(
            "<<FiletypeChanged>>", lambda *_: self._filetype_changed()
        )

        porcupine.utils.bind_with_data(
            self._tab.textwidget, "<<ContentChanged>>", self._content_changed
        )

    def _filetype_changed(self) -> None:
        raise RuntimeError("Don't change the filetype!!!")

    def _content_changed(self, event):
        self._version += 1

        start, end, range_length, new_text = event.data_tuple(
            str, str, int, str
        )
        start = tk_pos_to_lsp_pos(start)
        end = tk_pos_to_lsp_pos(end)

        self._client.notify(
            "textDocument/didChange",
            {
                "textDocument": {
                    "uri": tab_uri(self._tab),
                    "version": self._version,
                },
                "contentChanges": [
                    {
                        "text": new_text,
                        "range": {"start": start, "end": end},
                        "rangeLength": range_length,
                    }
                ],
            },
        )

        # TODO(PurpleMyst): Cancel the request if the user types more before we
        # get a response. This might be *very* hard.

    def _start_process(self):
        try:
            command = self.SERVER_COMMANDS[self._tab.filetype.name]
        except KeyError:
            return None

        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        return (process.stdin, process.stdout)

    def _porcufy_completion_item(self, item):
        if item.get("textEdit") is not None:
            start = lsp_pos_to_tk_pos(item["textEdit"]["range"]["start"])
            end = lsp_pos_to_tk_pos(item["textEdit"]["range"]["end"])
            new_text = item["textEdit"]["newText"]
        elif item.get("insertText") is not None:
            line, _ = map(int, self._tab.textwidget.index("insert").split("."))
            start, end = find_overlap_start(
                line,
                self._tab.textwidget.get("insert linestart", "insert"),
                item["insertText"],
            )
            new_text = item["insertText"]
        else:
            raise RuntimeError(
                "Completion item %r had neither textEdit nor insertText"
                % (item,)
            )

        return (start, end, new_text)

    def get_completions(self):
        self._client.request(
            "textDocument/completion",
            {
                "textDocument": {
                    "uri": tab_uri(self._tab),
                    "version": self._version,
                },
                "position": tab_position(self._tab),
            },
        )

        completion_items = self._completions_queue.get()
        for item in completion_items:
            yield self._porcufy_completion_item(item)
