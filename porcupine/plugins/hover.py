import tkinter
import dataclasses
from tkinter import ttk
from porcupine import utils, get_tab_manager, tabs


@dataclasses.dataclass
class Response(utils.EventDataclass):
    location: str
    text: str


class HoverManager:

    def __init__(self, tab: tabs.FileTab):
        self._tab = tab
        self._label = tkinter.Label(tab.textwidget, justify='left')
        self._location = tab.textwidget.index("insert")

    def on_hover_response(self, event: utils.EventWithData):
        response = event.data_class(Response     )
        print(response.location, self._location)
        if response.location        == self._location:
            if response.text        .strip() and 'underline_common' not in self._tab.textwidget.tag_names            (response.location):
                print("Hello world")
                self._label.configure(
                    text=response.text,
                    font=self._tab.textwidget["font"],
                    # opposite colors as in the text widget
                    bg=self._tab.textwidget["fg"],
                    fg=self._tab.textwidget["bg"],
                )
                x, y, width, height = self._tab.textwidget.bbox(self._location)
                self._label.place(x=x, y=y+height+10)
            else:
                self._label.place_forget()

    def _request_hover(self, location):
        if self._location != location:
            self._location = location
            self._label.place_forget()
            self._tab.textwidget.event_generate("<<HoverRequest>>", data=location)

    def on_mouse_move(self, event):
        self._request_hover    (self._tab       .textwidget     .index('current'))

    def on_cursor_move(self, event):
        self._request_hover    (self._tab       .textwidget     .index('insert'))


def on_new_filetab(tab: tabs.FileTab) -> None:
    manager = HoverManager(tab)
    tab.textwidget.bind("<Motion>", manager.on_mouse_move, add=True)
    tab.textwidget.bind("<<CursorMoved>>", manager.on_cursor_move, add=True)
    utils.bind_with_data(tab, "<<HoverResponse>>", manager.on_hover_response, add=True)


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
