# TODO: Instead of relying on a python language server to be running on
# localhost:8080, run our own one locally via subprocess
import socket
import os
import urllib.request
import typing as t
from collections import Counter

import sansio_lsp_client as lsp

import porcupine
from porcupine.tabs import Tab, FileTab

client: t.Optional[lsp.Client] = None
events: t.Optional[t.Iterator[lsp.Event]] = None

tab_versions: t.Counter[str] = Counter()


def tab_uri(tab: FileTab) -> str:
    return "file://" + urllib.request.pathname2url(os.path.abspath(tab.path))


def tab_text(tab: FileTab) -> str:
    return tab.textwidget.get("1.0", "end - 1 char")


def tab_position(tab: FileTab) -> lsp.Position:
    line, column = map(int, tab.textwidget.index("insert").split("."))
    return lsp.Position(line=line - 1, character=column)


def lsp_pos_to_tk_pos(pos: lsp.Position) -> str:
    return "{}.{}".format(pos.line + 1, pos.character)


def lsp_events(
    host: str = "localhost", port: int = 8080
) -> t.Iterator[lsp.Event]:
    sock = socket.socket()
    sock.connect((host, port))

    while True:
        sock.sendall(client.send())

        data = sock.recv(4096)
        if not data:
            break

        try:
            events = client.recv(data)
        except lsp.IncompleteResponseError:
            continue

        yield from events


def on_new_tab(event) -> None:
    tab: Tab = event.data_widget

    if isinstance(tab, FileTab):
        uri = tab_uri(tab)

        client.did_open(
            lsp.TextDocumentItem(
                uri=uri,
                languageId="Python",
                version=tab_versions[uri],
                text=tab_text(tab),
            )
        )

        porcupine.utils.bind_with_data(
            tab.textwidget,
            "<<ContentChanged>>",
            lambda _: on_tab_changed(tab),
            add=True,
        )

        on_file_type_changed(tab)
        porcupine.utils.bind_with_data(
            tab.textwidget,
            "<<FiletypeChanged>>",
            lambda e: on_file_type_changed(e.widget),
            add=True,
        )


def on_tab_changed(tab: FileTab) -> None:
    uri = tab_uri(tab)
    text = tab_text(tab)

    # FIXME: Only send the text that changed, not the whole new text.
    tab_versions[uri] += 1
    client.did_change(
        text_document=lsp.VersionedTextDocumentIdentifier(
            version=tab_versions[uri], uri=uri
        ),
        content_changes=[lsp.TextDocumentContentChangeEvent(text=text)],
    )

    for event in events:
        if isinstance(event, lsp.PublishDiagnostics):
            print("Diagnostics:")
            print(event)
            break
        else:
            print("Unknown event while waiting for diagnostics")
            print(event)


def completions(tab: FileTab) -> t.Iterator[t.Tuple[str, str, str]]:
    uri = tab_uri(tab)

    client.completions(
        text_document_position=lsp.TextDocumentPosition(
            textDocument=lsp.TextDocumentIdentifier(uri=uri),
            position=tab_position(tab),
        ),
        context=lsp.CompletionContext(
            triggerKind=lsp.CompletionTriggerKind.INVOKED
        ),
    )

    for event in events:
        if isinstance(event, lsp.Completion):
            items = event.completion_list.items

            for item in items:
                text_edit: lsp.TextEdit = item.textEdit

                start = lsp_pos_to_tk_pos(text_edit.range.start)
                end = lsp_pos_to_tk_pos(text_edit.range.end)

                yield (start, end, text_edit.newText)
        else:
            print("Unknown event while completing")
            print(event)


def on_file_type_changed(tab: FileTab) -> None:
    if tab.filetype.name == "Python":
        tab.completer = completions
    elif tab.completer is completions:
        tab.completer = None

def setup():
    global client, events
    client = lsp.Client()
    events = lsp_events()

    for event in events:
        if isinstance(event, lsp.Initialized):
            break
        else:
            print("Unknown event while initializing")
            print(event)

    tab_manager = porcupine.get_tab_manager()
    porcupine.utils.bind_with_data(
        tab_manager, "<<NewTab>>", on_new_tab, add=True
    )
