from __future__ import annotations

import dataclasses
import tkinter

from porcupine import get_main_window, get_tab_manager, tabs, utils


@dataclasses.dataclass
class Response(utils.EventDataclass):
    location: str
    text: str


class HoverManager:
    def __init__(self, textwidget: tkinter.Text):
        self.textwidget = textwidget
        self._label: tkinter.Label | None = None
        self._location = textwidget.index("insert")

    def hide_label(self, junk: object = None) -> None:
        if self._label is not None:
            self._label.destroy()
            self._label = None

    def _show_label(self, message: str) -> None:
        self.hide_label()

        bbox = self.textwidget.bbox(self._location)
        if bbox is None:
            # this is called even though the relevant part of text isn't visible? weird
            return

        bbox_x, bbox_y, bbox_width, bbox_height = bbox
        gap_size = 8

        self._label = tkinter.Label(
            self.textwidget,
            text=message,
            wraplength=(self.textwidget.winfo_width() - 2 * gap_size),
            justify="left",
            # opposite colors as in the text widget
            bg=self.textwidget["fg"],
            fg=self.textwidget["bg"],
        )

        label_width = self._label.winfo_reqwidth()
        label_height = self._label.winfo_reqheight()

        # don't go beyond the right edge of textwidget
        label_x = min(bbox_x, self.textwidget.winfo_width() - gap_size - label_width)

        if bbox_y + bbox_height + gap_size + label_height < self.textwidget.winfo_height():
            # label goes below bbox
            label_y = bbox_y + bbox_height + gap_size
        else:
            # would go below bottom of text widget, let's put it above instead
            label_y = bbox_y - gap_size - label_height
        self._label.place(x=label_x, y=label_y)

    def on_hover_response(self, event: utils.EventWithData) -> None:
        response = event.data_class(Response)
        if response.location == self._location:
            if response.text.strip():
                self._show_label(response.text)
            else:
                self.hide_label()

    def _request_hover(self, location: str) -> None:
        if self._location != location:
            self._location = location
            self.hide_label()
            self.textwidget.event_generate("<<HoverRequest>>", data=location)

    def on_mouse_move(self, junk_event: object) -> None:
        self._request_hover(self.textwidget.index("current"))

    def on_cursor_move(self, junk_event: object) -> None:
        self._request_hover(self.textwidget.index("insert"))


def on_new_filetab(tab: tabs.FileTab) -> None:
    manager = HoverManager(tab.textwidget)
    tab.textwidget.bind("<<HoverHide>>", manager.hide_label, add=True)
    utils.add_scroll_command(tab.textwidget, "yscrollcommand", manager.hide_label)

    tab.textwidget.bind("<Motion>", manager.on_mouse_move, add=True)
    tab.textwidget.bind("<<CursorMoved>>", manager.on_cursor_move, add=True)
    utils.bind_with_data(tab.textwidget, "<<HoverResponse>>", manager.on_hover_response, add=True)


def hide_all_hovers(event: tkinter.Event[tkinter.Misc]) -> None:
    if event.widget is get_main_window():  # Tk and Toplevel events need this check
        for tab in get_tab_manager().tabs():
            if isinstance(tab, tabs.FileTab):
                tab.textwidget.event_generate("<<HoverHide>>")


def setup() -> None:
    # trigger <<HoverHide>> when text widget goes invisible (e.g. switching tabs)
    get_main_window().event_add("<<HoverHide>>", "<Unmap>")

    # and when the entire porcupine window loses input focus (binding here to avoid unbinding)
    get_main_window().bind("<FocusOut>", hide_all_hovers, add=True)

    get_tab_manager().add_filetab_callback(on_new_filetab)
