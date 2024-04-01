"""Display a status bar in each file tab."""
from __future__ import annotations

import tkinter
import unicodedata
from tkinter import ttk

from porcupine import get_main_window, get_tab_manager, settings, tabs, utils
from porcupine.textutils import count


class StatusBar(ttk.Frame):
    def __init__(self, tab: tabs.FileTab):
        super().__init__(tab.bottom_frame, name="statusbar")
        self._tab = tab

        self._top_frame = ttk.Frame(self)
        self._top_frame.pack(fill="x")

        # packing order chosen so that if the path is long, everything else
        # disappears before path truncates
        self.path_label = ttk.Label(self._top_frame)
        self.path_label.pack(side="left")

        self._showing_special_message = False

        self._line_ending_button = ttk.Button(
            self._top_frame, command=self._choose_line_ending, style="Statusbar.TButton", width=0
        )
        self._line_ending_button.pack(side="right", padx=2)
        self._encoding_button = ttk.Button(
            self._top_frame, command=self._choose_encoding, style="Statusbar.TButton", width=0
        )
        self._encoding_button.pack(side="right", padx=2)

        self.selection_label = ttk.Label(self)
        self.selection_label.pack(side="left")

    def update_labels(self, junk: object = None) -> None:
        if not self._showing_special_message:
            self.path_label.config(text=str(self._tab.path or "File not saved yet"))

        try:
            chars = count(self._tab.textwidget, "sel.first", "sel.last")
            # If the cursor is in beginning of line, don't count that as another line
            lines = count(self._tab.textwidget, "sel.first", "sel.last - 1 char", option="-lines")
            lines += 1
        except tkinter.TclError:
            # no text selected
            line, column = self._tab.textwidget.index("insert").split(".")
            self.selection_label.config(text=f"Line {line}, column {column}")
        else:
            if chars == 1:
                char = self._tab.textwidget.get("sel.first")
                hex_codepoint = hex(ord(char))[2:]
                if ord(char) in range(128):
                    # Non-hex also displayed in case you are debugging c code with printf
                    text = f"ASCII character {ord(char)} (hex {hex_codepoint})"
                else:
                    text = f"Unicode character U+{hex_codepoint.upper()}: {unicodedata.name(char)}"
            else:
                words = len(self._tab.textwidget.get("sel.first", "sel.last").split())
                text = f"{chars} characters"
                if words >= 2:
                    text += f" ({words} words)"
                if lines >= 2:
                    text += f" on {lines} lines"
                text += " selected"
            self.selection_label.config(text=text)

        self._encoding_button.config(text=self._tab.settings.get("encoding", str))
        self._line_ending_button.config(
            text=self._tab.settings.get("line_ending", settings.LineEnding).name
        )

    def show_special_message(self, text: str) -> None:
        self.path_label.config(text=text)
        self._showing_special_message = True

    def show_reload_warning(self, event: utils.EventWithData) -> None:
        if event.data_class(tabs.ReloadInfo).had_unsaved_changes:
            oops = utils.get_binding("<<Undo>>")
            text = f"File was reloaded with unsaved changes. Press {oops} to get your changes back."
            self.show_special_message(text)
            self.path_label.config(foreground="red")

    def clear_special_message(self, junk: object) -> None:
        self.path_label.config(foreground="")
        self._showing_special_message = False
        self.update_labels()

    def _choose_encoding(self) -> None:
        new_encoding = utils.ask_encoding(
            "Choose an encoding:", self._tab.settings.get("encoding", str)
        )
        if new_encoding is not None:
            self._tab.settings.set("encoding", new_encoding)

    def _choose_line_ending(self) -> None:
        if get_main_window().tk.call("winfo", "exists", ".choose_line_ending"):
            get_main_window().tk.call("focus", ".choose_line_ending")
            return

        old_value = self._tab.settings.get("line_ending", settings.LineEnding)
        self._tab.settings.set("line_ending", utils.ask_line_ending(old_value))


_global_message: str | None = None


def set_global_message(message: str | None) -> None:
    """Display a message whenever a new tab is opened.

    This is currently used for notifying the user about a new Porcupine
    version. Feel free to expand the status bar's API a lot beyond this
    if you need something more advanced.
    """
    global _global_message
    _global_message = message


def _on_new_filetab(tab: tabs.FileTab) -> None:
    statusbar = StatusBar(tab)
    statusbar.pack(side="bottom", fill="x")
    if _global_message is not None:
        statusbar.show_special_message(_global_message)

    utils.bind_with_data(tab, "<<Reloaded>>", statusbar.show_reload_warning, add=True)
    tab.bind("<<AfterSave>>", statusbar.clear_special_message, add=True)

    tab.bind("<<PathChanged>>", statusbar.update_labels, add=True)
    tab.bind("<<TabSettingChanged:encoding>>", statusbar.update_labels, add=True)
    tab.bind("<<TabSettingChanged:line_ending>>", statusbar.update_labels, add=True)
    tab.textwidget.bind("<<CursorMoved>>", statusbar.update_labels, add=True)
    tab.textwidget.bind("<<Selection>>", statusbar.update_labels, add=True)
    statusbar.update_labels()


def _update_button_style(junk_event: object = None) -> None:
    # https://tkdocs.com/tutorial/styles.html
    # tkinter's style stuff sucks
    get_tab_manager().tk.eval(
        "ttk::style configure Statusbar.TButton -padding {10 0} -anchor center"
    )


def setup() -> None:
    get_tab_manager().add_filetab_callback(_on_new_filetab)

    get_tab_manager().bind("<<ThemeChanged>>", _update_button_style, add=True)
    _update_button_style()
