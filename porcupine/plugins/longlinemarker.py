"""Maximum line length marker."""
from __future__ import annotations

import sys
import tkinter
import tkinter.font as tkfont

from pygments import styles, token

from porcupine import get_tab_manager, settings, tabs, textutils, utils

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


class LongLineMarker:
    def __init__(self, filetab: tabs.FileTab) -> None:
        self.tab = filetab

        # this must not be a ttk frame because the background color
        # comes from the pygments style, not from the ttk theme
        self.frame = tkinter.Frame(filetab.textwidget, width=1)

    def setup(self) -> None:
        # xscrollcommand runs when the text widget resizes
        utils.add_scroll_command(self.tab.textwidget, "xscrollcommand", self.do_update)
        self.tab.bind("<<TabSettingChanged:max_line_length>>", self.do_update, add=True)
        self.tab.bind("<<SettingChanged:font_family>>", self.do_update, add=True)
        self.tab.bind("<<SettingChanged:font_size>>", self.do_update, add=True)
        self.tab.bind("<<SettingChanged:pygments_style>>", self.on_style_changed, add=True)

        self.do_update()
        self.on_style_changed()

    def do_update(self, *junk: object) -> None:
        max_line_length = self.tab.settings.get("max_line_length", int)
        if max_line_length <= 0:
            # marker is disabled
            self.frame.place_forget()
            return

        width, height = textutils.textwidget_size(self.tab.textwidget)

        font = tkfont.Font(name=self.tab.textwidget["font"], exists=True)
        font_x = font.measure(" " * max_line_length)

        scroll_start, scroll_end = self.tab.textwidget.xview()  # type: ignore[no-untyped-call]
        relative_scroll_start = scroll_start / (scroll_end - scroll_start)
        scroll_x = relative_scroll_start * width

        self.frame.place(x=(font_x - scroll_x), y=0, height=height)

    def on_style_changed(self, junk: object = None) -> None:
        style = styles.get_style_by_name(settings.get("pygments_style", str))
        infos = dict(iter(style))  # iterating is documented
        for tokentype in [token.Error, token.Name.Exception]:
            if tokentype in infos:
                keys: list[Literal["bgcolor", "color", "border"]] = ["bgcolor", "color", "border"]
                for key in keys:
                    value = infos[tokentype][key]
                    if value is not None:
                        self.frame.config(bg=("#" + value))
                        return

        # stupid fallback
        self.frame.config(bg="red")


def on_new_filetab(tab: tabs.FileTab) -> None:
    # raymond hettinger says 90-ish
    tab.settings.add_option("max_line_length", 90)
    LongLineMarker(tab).setup()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
