"""Display a status bar in each file tab."""
import tkinter
import unicodedata
from tkinter import ttk
from typing import Callable

from porcupine import get_tab_manager, settings, tabs, utils
from porcupine.textutils import count


# ttk.Button contains too much padding
class SmallButton(ttk.Label):
    def __init__(self, parent: tkinter.Misc, on_click: Callable[[], None]):
        super().__init__(parent, relief="raised")
        self._on_click = on_click
        self.bind("<Button-1>", self._on_press, add=True)
        self.bind("<ButtonRelease-1>", self._on_release, add=True)

    def _on_press(self, event):
        self["relief"] = "sunken"

    def _on_release(self, event):
        self["relief"] = "raised"
        self._on_click()


class StatusBar(ttk.Frame):
    def __init__(self, tab: tabs.FileTab):
        super().__init__(tab.bottom_frame)
        self._tab = tab

        self._top_frame = ttk.Frame(self)
        self._top_frame.pack(fill="x")

        # packing order chosen so that if the path is long, everything else
        # disappears before path truncates
        self._path_label = ttk.Label(self._top_frame)
        self._path_label.pack(side="left")
        self._line_ending_button = SmallButton(self._top_frame, self._choose_line_ending)
        self._line_ending_button.pack(side="right", padx=2)
        self._encoding_button = SmallButton(self._top_frame, self._choose_encoding)
        self._encoding_button.pack(side="right", padx=2)

        self._selection_label = ttk.Label(
            self, text="Non-ASCII character: U+D6 LATIN CAPITAL LETTER O WITH DIAERESIS"
        )
        self._selection_label.pack(side="left")

    def update_labels(self, junk: object = None) -> None:
        self._path_label.config(text=str(self._tab.path or "File not saved yet"))

        try:
            # For line count, if the cursor is in beginning of line, don't count that as another line.
            chars = count(self._tab.textwidget, "sel.first", "sel.last")
            lines = count(self._tab.textwidget, "sel.first", "sel.last - 1 char", option="-lines")
        except tkinter.TclError:
            # no text selected
            line, column = self._tab.textwidget.index("insert").split(".")
            self._selection_label.config(text=f"Line {line}, column {column}")
        else:
            if chars == 1:
                char = self._tab.textwidget.get("sel.first")
                hex_codepoint = hex(ord(char))[2:]
                if ord(char) in range(128):
                    # Non-hex also displayed in case you are debugging c code with printf
                    text = f"ASCII character {ord(char)} (hex {hex_codepoint})"
                else:
                    text = f"Unicode character U+{hex_codepoint.upper()}: {unicodedata.name(char)}"
            elif lines == 0:
                text = f"{chars} characters selected"
            else:
                text = f"{chars} characters on {lines+1} lines selected"
            self._selection_label.config(text=text)

        self._encoding_button.config(text=self._tab.settings.get("encoding", str))
        self._line_ending_button.config(
            text=self._tab.settings.get("line_ending", settings.LineEnding).name
        )

    def show_reload_warning(self, event: utils.EventWithData) -> None:
        if event.data_class(tabs.ReloadInfo).had_unsaved_changes:
            oops = utils.get_binding("<<Undo>>")
            text = f"File was reloaded with unsaved changes. Press {oops} to get your changes back."
            self._path_label.config(foreground="red", text=text)

    def clear_reload_warning(self, junk: object) -> None:
        if self._path_label["foreground"]:
            self._path_label.config(foreground="")
            self._update_labels()

    def _choose_encoding(self):
        new_encoding = utils.ask_encoding(
            "Choose the encoding:", self._tab.settings.get("encoding", str)
        )
        if new_encoding is not None:
            self._tab.settings.set("encoding", new_encoding)

    def _choose_line_ending(self):
        raise NotImplementedError


def on_new_filetab(tab: tabs.FileTab) -> None:
    statusbar = StatusBar(tab)
    statusbar.pack(side="bottom", fill="x")

    utils.bind_with_data(tab, "<<Reloaded>>", statusbar.show_reload_warning, add=True)
    tab.textwidget.bind("<<ContentChanged>>", statusbar.clear_reload_warning, add=True)

    tab.bind("<<PathChanged>>", statusbar.update_labels, add=True)
    tab.bind("<<TabSettingChanged:encoding>>", statusbar.update_labels, add=True)
    tab.bind("<<TabSettingChanged:line_ending>>", statusbar.update_labels, add=True)
    tab.textwidget.bind("<<CursorMoved>>", statusbar.update_labels, add=True)
    tab.textwidget.bind("<<Selection>>", statusbar.update_labels, add=True)
    statusbar.update_labels()


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)
