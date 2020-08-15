"""Show red and yellow underlines to indicate errors and warnings in the code.

To use this plugin, you also need some other plugin such as the langserver plugin.
"""

import dataclasses
from functools import partial
import tkinter
from typing import Dict, List, Optional

from porcupine import get_tab_manager, tabs, utils


@dataclasses.dataclass
class Underline:
    start: str
    end: str
    message: str
    is_error: bool


@dataclasses.dataclass
class UnderlineList(utils.EventDataclass):
    underlines: List[Underline]


def _tag_spans_multiple_lines(textwidget: tkinter.Text, tag: str) -> bool:
    first_lineno: str = textwidget.index(f'{tag}.first')[0]
    last_lineno: str = textwidget.index(f'{tag}.last')[0]
    return (first_lineno != last_lineno)


class _Underliner:

    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        self.textwidget.bind('<Unmap>', self._hide_popup, add=True)
        self.textwidget.bind('<<CursorMoved>>', self._on_cursor_moved, add=True)
        self._popup: Optional[tkinter.Toplevel] = None
        self._currently_showing_tag: Optional[str] = None
        self._currently_tagged: Dict[str, Underline] = {}
        self._bindings: List[str] = []

    def set_underlines(self, event: utils.EventWithData) -> None:
        self._hide_popup()

        for tag in self._currently_tagged.keys():
            self.textwidget.tag_delete(tag)
        self._currently_tagged.clear()

        for binding in self._bindings:
            self.textwidget.deletecommand(binding)
        self._bindings.clear()

        for index, underline in enumerate(event.data_class(UnderlineList).underlines):
            tag = f'underline{index}'
            self._currently_tagged[tag] = underline

            self.textwidget.tag_config(
                tag,
                underline=True,
                underlinefg=('red' if underline.is_error else 'orange'),
            )
            self.textwidget.tag_add(tag, underline.start, underline.end)
            self._bindings.append(self.textwidget.tag_bind(tag, '<Enter>', partial(self._show_popup, tag)))
            self._bindings.append(self.textwidget.tag_bind(tag, '<Leave>', self._hide_popup))

    def _on_cursor_moved(self, junk: object) -> None:
        for tag in self.textwidget.tag_names('insert'):
            if tag in self._currently_tagged:
                self._show_popup(tag)
                return

        self._hide_popup()

    def _show_popup(self, tag: str, junk: object = None) -> None:
        if tag == self._currently_showing_tag:
            return

        self._hide_popup()

        if _tag_spans_multiple_lines(self.textwidget, tag):
            bbox = self.textwidget.bbox(f'{tag}.last linestart')
        else:
            bbox = self.textwidget.bbox(f'{tag}.first')

        if bbox is None:
            # this is called even though the relevant part of text isn't visible? weird
            return

        x, y, width, height = bbox
        x += self.textwidget.winfo_rootx()
        y += self.textwidget.winfo_rooty()

        self._currently_showing_tag = tag
        self._popup = tkinter.Toplevel()
        tkinter.Label(
            self._popup,
            text=self._currently_tagged[tag].message,
            # opposite colors as in the text widget
            bg=self.textwidget['fg'],
            fg=self.textwidget['bg'],
        ).pack()
        self._popup.geometry(f'+{x}+{y + height + 5}')
        self._popup.overrideredirect(True)

    def _hide_popup(self, junk: object = None) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
            self._currently_showing_tag = None


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        underliner = _Underliner(tab.textwidget)
        utils.bind_with_data(tab, '<<SetUnderlines>>', underliner.set_underlines, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
