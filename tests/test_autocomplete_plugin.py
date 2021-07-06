from porcupine import utils
from porcupine.plugins.autocomplete import Completion, Response


def test_pasteId_lastPasteId(filetab):
    events = []
    utils.bind_with_data(filetab, "<<AutoCompletionResponse>>", events.append, add=False)
    filetab.textwidget.insert("1.0", "pasteId lastPasteId lastPasteId lastPasteId past")
    filetab.textwidget.mark_set("insert", "end - 1 char")

    filetab.textwidget.event_generate("<Tab>")
    [event] = events
    assert event.data_class(Response).completions == [
        Completion(
            display_text="pasteId",
            replace_start="1.44",
            replace_end="1.48",
            replace_text="pasteId",
            filter_text="pasteId",
            documentation="pasteId",
        ),
        Completion(
            display_text="lastPasteId",
            replace_start="1.44",
            replace_end="1.48",
            replace_text="lastPasteId",
            filter_text="lastPasteId",
            documentation="lastPasteId",
        ),
    ]
