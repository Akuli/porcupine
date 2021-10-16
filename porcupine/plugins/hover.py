from __future__ import annotations

import dataclasses
import tkinter

from porcupine import get_main_window, get_tab_manager, tabs, textutils, utils


# Data of request is a text widget location. Use event.data_string to access it.
@dataclasses.dataclass
class Response(utils.EventDataclass):
    location: str
    text: str


class HoverManager:
    def __init__(self, textwidget: tkinter.Text):
        self._textwidget = textwidget
        self._label: tkinter.Label | None = None
        self._location = textwidget.index("insert")

    def hide_label(self, junk: object = None) -> None:
        if self._label is not None:
            self._label.destroy()
            self._label = None

    def _show_label(self, message: str) -> None:
        self.hide_label()
        self._label = tkinter.Label(
            self._textwidget,
            text=message,
            justify="left",
            # some hack to get a fitting popup bg
            bg=utils.mix_colors(
                self._textwidget["bg"], self._textwidget["fg"], 0.8
            ),
            fg=self._textwidget["fg"],
        )
        textutils.place_popup(
            self._textwidget,
            self._label,
            width=min(self._label.winfo_reqwidth(), self._textwidget.winfo_width() // 2),
            text_position=self._location,
            wrap=True,
        )

    def _request_hover(self, location: str) -> None:
        if self._location != location:
            self._location = location
            self.hide_label()
            self._textwidget.event_generate("<<HoverRequest>>", data=location)

    def on_mouse_move(self, junk_event: object) -> None:
        self._request_hover(self._textwidget.index("current"))

    def on_cursor_move(self, junk_event: object) -> None:
        self._request_hover(self._textwidget.index("insert"))

    def on_hover_response(self, event: utils.EventWithData) -> None:
        response = event.data_class(Response)
        if response.location != self._location:
            # User touched something while waiting for response, new request sent
            return

        if response.text.strip() and self._textwidget.focus_get() == self._textwidget:
            if response.text.count("\n") > 10:
                text = "\n".join(response.text.split("\n")[:10]) + "\n..."
            else:
                text = response.text
            self._show_label(text)
        else:
            self.hide_label()


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
