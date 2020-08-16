"""Show underlines in code to indicate different things.

Currently the langserver plugin displaying errors and warnings with this plugin
and the urls plugin uses this to create control-clickable links.
"""

import dataclasses
import tkinter
from typing import Dict, List, Optional

from porcupine import get_tab_manager, tabs, utils


@dataclasses.dataclass
class Underline:
    start: str
    end: str
    message: str
    color: Optional[str] = None


@dataclasses.dataclass
class Underlines(utils.EventDataclass):
    # <<SetUnderlines>> clears previous underlinings with the same id
    id: str
    underline_list: List[Underline]


def _tag_spans_multiple_lines(textwidget: tkinter.Text, tag: str) -> bool:
    first_lineno: str = textwidget.index(f'{tag}.first')[0]
    last_lineno: str = textwidget.index(f'{tag}.last')[0]
    return (first_lineno != last_lineno)


class _Underliner:

    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        self.textwidget.bind('<<CursorMoved>>', self._on_cursor_moved, add=True)
        self.textwidget.bind('<Unmap>', self._hide_popup, add=True)
        self.textwidget.tag_bind('underline_common', '<Enter>', self._on_mouse_enter)
        self.textwidget.tag_bind('underline_common', '<Leave>', self._hide_popup)

        self._popup: Optional[tkinter.Toplevel] = None
        self._popup_tag: Optional[str] = None
        self._tag2underline: Dict[str, Underline] = {}

    def _show_tag_at_index(self, index: str) -> None:
        for tag in self.textwidget.tag_names(index):
            if tag in self._tag2underline:
                self._show_popup(tag)
                return
        self._hide_popup()

    def _on_mouse_enter(self, junk: object) -> None:
        self._show_tag_at_index('current')

    def _on_cursor_moved(self, junk: object) -> None:
        self._show_tag_at_index('insert')

    def set_underlines(self, event: utils.EventWithData) -> None:
        underlines = event.data_class(Underlines)
        self.textwidget.tag_remove(f'underline:{underlines.id}', '1.0', 'end')

        old_underlines_deleted = False
        for tag in list(self._tag2underline.keys()):
            literally_underline, tag_id, number = tag.split(':')
            if tag_id == underlines.id:
                self.textwidget.tag_delete(tag)
                del self._tag2underline[tag]
                old_underlines_deleted = True

        for index, underline in enumerate(underlines.underline_list):
            tag = f'underline:{underlines.id}:{index}'
            less_specific_tag = f'underline:{underlines.id}'

            self._tag2underline[tag] = underline
            if underline.color is None:
                self.textwidget.tag_config(tag, underline=True)
            else:
                self.textwidget.tag_config(tag, underline=True, underlinefg=underline.color)

            self.textwidget.tag_add(tag, underline.start, underline.end)
            self.textwidget.tag_add(less_specific_tag, underline.start, underline.end)

        # Updating underline_common tag is kind of brute-force because overlapping non-common
        # underline tags make it difficult. But let's not run it at every key press unless something
        # actually changed.
        if old_underlines_deleted or underlines.underline_list:
            self.textwidget.tag_remove('underline_common', '1.0', 'end')
            for tag in self._tag2underline.keys():
                ranges = self.textwidget.tag_ranges(tag)
                for start, end in zip(ranges[0::2], ranges[1::2]):
                    self.textwidget.tag_add('underline_common', start, end)

    def _show_popup(self, tag: str) -> None:
        if self._popup_tag == tag:
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

        self._popup_tag = tag
        self._popup = tkinter.Toplevel()
        tkinter.Label(
            self._popup,
            text=self._tag2underline[tag].message,
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
            self._popup_tag = None


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        underliner = _Underliner(tab.textwidget)
        utils.bind_with_data(tab, '<<SetUnderlines>>', underliner.set_underlines, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
