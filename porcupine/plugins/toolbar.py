"""Display a toolbar in each file tab."""
from __future__ import annotations

import dataclasses
import logging
from functools import partial
from tkinter import ttk
from typing import Callable, Iterable

from porcupine import get_tab_manager, tabs

log = logging.getLogger(__name__)

setup_after = ["filetypes"]


# TODO: add icon (make text optional?)
@dataclasses.dataclass(kw_only=True)
class Button:
    text: str
    description: str | None = None
    command: Callable


@dataclasses.dataclass(kw_only=True)
class ButtonGroup:
    name: str
    priority: int  # 0 is highest
    buttons: list[Button]
    separator: bool = True


class SortedButtonGroupList(list[ButtonGroup]):
    """A of button groups that sorts itself automatically"""

    # no this wasn't necessary, but I am in too deep to stop now
    # but seriously why isn't there a sorted list type in the stdlib?
    @classmethod
    def _key_func(cls, group: ButtonGroup) -> int:
        return group.priority

    def __init__(self, *args: Iterable[ButtonGroup], **kwargs: ButtonGroup) -> None:
        super().__init__(*args, **kwargs)
        self.sort(key=self._key_func)

    def append(self, __item: ButtonGroup) -> None:
        super().append(__item)
        self.sort(key=self._key_func)

    def extend(self, __iterable: Iterable[ButtonGroup]) -> None:
        super().extend(__iterable)
        self.sort(key=self._key_func)


filetype_button_groups_mapping: dict[str, SortedButtonGroupList] = {}


def add_button_group(
    *, filetype_name: str, name: str, buttons: list[Button], priority: int = 0, separator=True
) -> None:
    button_group = ButtonGroup(name=name, priority=priority, buttons=buttons, separator=separator)
    if filetype_button_groups_mapping.get(filetype_name):
        filetype_button_groups_mapping[filetype_name].append(button_group)
    else:
        filetype_button_groups_mapping[filetype_name] = SortedButtonGroupList([button_group])


class ToolBar(ttk.Frame):
    def __init__(self, tab: tabs.FileTab):
        super().__init__(tab.top_frame, name="toolbar", border=1, relief="raised")
        self._tab = tab

    def update_buttons(self, tab: tabs.FileTab, junk: object = None) -> None:
        """Different filetypes have different buttons associated with them."""
        filetype_name = tab.settings.get("filetype_name", object)
        button_groups = filetype_button_groups_mapping.get(filetype_name)
        if not button_groups:
            return

        for button_group in button_groups:
            for button in button_group.buttons:
                ttk.Button(
                    self,
                    command=partial(button.command, tab),
                    style="Statusbar.TButton",
                    text=button.text,
                ).pack(side="left", padx=10, pady=5)


def on_new_filetab(tab: tabs.FileTab) -> None:
    toolbar = ToolBar(tab)
    toolbar.pack(side="bottom", fill="x")

    tab.bind("<<TabSettingChanged:filetype_name>>", partial(toolbar.update_buttons, tab), add=True)
    toolbar.update_buttons(tab)


def update_button_style(junk_event: object = None) -> None:
    # https://tkdocs.com/tutorial/styles.html
    # tkinter's style stuff sucks
    get_tab_manager().tk.eval(
        "ttk::style configure Statusbar.TButton -padding {10 0} -anchor center"
    )


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
    get_tab_manager().bind("<<ThemeChanged>>", update_button_style, add=True)
    update_button_style()
