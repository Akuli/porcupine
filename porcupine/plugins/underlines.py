"""Show red and yellow underlines to indicate errors and warnings in the code.

To use this plugin, you also need some other plugin such as the langserver plugin.
"""

import dataclasses
from functools import partial
import tkinter
from typing import List, Optional

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
        self._popup: Optional[tkinter.Toplevel] = None
        self._tags: List[str] = []

    def set_underlines(self, event: utils.EventWithData) -> None:
        self._hide_popup()

        for tag in self._tags:
            self.textwidget.tag_delete(tag)
        self._tags.clear()

        for index, underline in enumerate(event.data_class(UnderlineList).underlines):
            tag = f'underline{index}'
            self._tags.append(tag)

            self.textwidget.tag_config(
                tag,
                underline=True,
                underlinefg=('red' if underline.is_error else 'orange'),
            )
            self.textwidget.tag_add(tag, underline.start, underline.end)
            self.textwidget.tag_bind(tag, '<Enter>', partial(self._show_popup, tag, underline.message))
            self.textwidget.tag_bind(tag, '<Leave>', self._hide_popup)

    def _show_popup(self, tag: str, message: str, junk: object) -> None:
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

        # TODO: similar code in utils.set_tooltip()
        self._popup = tkinter.Toplevel()
        tkinter.Label(
            self._popup,
            text=message,
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


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        underliner = _Underliner(tab.textwidget)
        utils.bind_with_data(tab, '<<SetUnderlines>>', underliner.set_underlines, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
