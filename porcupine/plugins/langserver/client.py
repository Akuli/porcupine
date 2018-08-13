import sys
import threading
import queue

import kieli

import porcupine
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

        self._initialize_response_event = threading.Event()
        self._completions_queue = queue.Queue()

        self._client = kieli.LSPClient()
        self._client.response_handler("initialize")(self._initialize_response)
        self._client.notification_handler("textDocument/publishDiagnostics")(
            self._publish_diagnostics
        )
        self._client.response_handler("textDocument/completion")(
            self._completions_response
        )

        command = self.SERVER_COMMANDS[self.tab.filetype.name]

        if command is None:
            print("No command is known for", self.tab.filetype.name)
            return

        self._client.connect_to_process(*command)
        self._client.request(
            "initialize",
            {"rootUri": None, "processId": None, "capabilities": {}},
        )

        def _on_initialize_response(success, data):
            assert success, data

            self._client.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": tab_uri(self.tab),
                        "languageId": self.tab.filetype.name.lower(),
                        "version": self._version,
                        "text": tab_text(self.tab),
                    }
                },
            )

            self.tab.completer = lambda *_: self.get_completions()

            # TODO(PurpleMyst): Initialization takes forever. While a printout
            # is fine for development, we probably should add a little spinny
            # thing somewhere.
            print(
                "Language server for {!r} is initialized.".format(
                    self.tab.path
                )
            )

            self.tab.bind(
                "<<FiletypeChanged>>", lambda *_: self._on_filetype_changed()
            )

            porcupine.utils.bind_with_data(
                self.tab.textwidget,
                "<<ContentChanged>>",
                self._content_changed,
            )

        porcupine.utils.run_in_thread(
            self._initialize_response_event.wait, _on_initialize_response
        )

    def _publish_diagnostics(self, notification):
        print("Diagnostics:", notification.params, sep="\n")

    def _completions_response(self, _request, response):
        print("Completions response:", response)

        assert not response.result["isIncomplete"]
        self._completions_queue.put(response.result["items"])

    def _initialize_response(self, _request, _response):
        self._initialize_response_event.set()

    def _on_filetype_changed(self) -> None:
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
                    "uri": tab_uri(self.tab),
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

    def _porcufy_completion_item(self, item):
        if "textEdit" in item:
            edit = item["textEdit"]
            edit_range = edit["range"]

            start = lsp_pos_to_tk_pos(edit_range["start"])
            end = lsp_pos_to_tk_pos(edit_range["end"])
            new_text = edit["newText"]
        elif "insertText" in item:
            new_text = item["insertText"]

            line, _ = map(int, self.tab.textwidget.index("insert").split("."))
            start, end = find_overlap_start(
                line,
                self.tab.textwidget.get("insert linestart", "insert"),
                new_text,
            )
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
                    "uri": tab_uri(self.tab),
                    "version": self._version,
                },
                "position": tab_position(self.tab),
            },
        )

        completion_items = self._completions_queue.get()
        for item in completion_items:
            yield self._porcufy_completion_item(item)
