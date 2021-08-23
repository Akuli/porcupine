"""Display a status bar in each file tab."""
from __future__ import annotations

import tkinter
import unicodedata
from tkinter import ttk

from porcupine import get_main_window, get_tab_manager, settings, tabs, utils
from porcupine.textutils import count


# Must be in a function because lambdas and local variables are ... inconvenient
def _connect_label_to_radiobutton(label: ttk.Label, radio: ttk.Radiobutton) -> None:
    label.bind("<Enter>", lambda e: radio.event_generate("<Enter>"), add=True)
    label.bind("<Leave>", lambda e: radio.event_generate("<Leave>"), add=True)
    label.bind("<Button-1>", lambda e: radio.invoke(), add=True)  # type: ignore[no-untyped-call]


def ask_line_ending(old_line_ending: settings.LineEnding) -> settings.LineEnding:
    top = tkinter.Toplevel()
    top.resizable(False, False)
    top.transient(get_main_window())

    big_frame = ttk.Frame(top)
    big_frame.pack(fill="both", expand=True)
    ttk.Label(big_frame, text="Choose how line endings should be saved:").pack(
        fill="x", padx=5, pady=5
    )

    options: list[tuple[str, str, str]] = [
        (
            "LF",
            "LF line endings (Unix)",
            "Newline characters will be saved to the file as the LF byte (\\n)."
            " This is the line ending used by most Unix-like operating systems,"
            " such as Linux and MacOS,"
            " and usually the preferred line ending in projects that use Git.",
        ),
        (
            "CRLF",
            "CRLF line endings (Windows)",
            "Each newline will be saved to the file as two bytes,"
            " CR (\\r) followed by LF (\\n)."
            " CRLF is Porcupine's default line ending on Windows,"
            " and the only line ending supported by many Windows programs."
            "\n\nCommitting files to Git with CRLF is usually considered bad style."
            " If you use CRLF in projects that use Git,"
            " make sure to configure Git to convert the line endings"
            " so that your CRLF line endings appear as LF line endings"
            " for other people working on the project.",
        ),
        (
            "CR",
            "CR line endings (???)",
            "I don't know when this option could be useful,"
            " but it is provided in case you have some use case that I didn't think of.",
        ),
    ]

    var = tkinter.StringVar(value=old_line_ending.name)
    for line_ending_name, short_text, long_text in options:
        radio = ttk.Radiobutton(big_frame, variable=var, value=line_ending_name, text=short_text)
        radio.pack(fill="x", padx=(10, 0), pady=(10, 0))
        label = ttk.Label(big_frame, wraplength=450, text=long_text)
        label.pack(fill="x", padx=(50, 10), pady=(0, 10))
        _connect_label_to_radiobutton(label, radio)

    ttk.Label(
        big_frame,
        text=(
            "Consider setting the line ending in a project-specific .editorconfig file"
            " if your project uses unusual choice of line endings."
        ),
    )

    ttk.Button(big_frame, text="OK", command=top.destroy).pack(side="right", padx=10, pady=10)
    top.bind("<Return>", (lambda e: top.destroy()), add=True)
    top.bind("<Escape>", (lambda e: top.destroy()), add=True)

    top.wait_window()
    return settings.LineEnding[var.get()]


class StatusBar(ttk.Frame):
    def __init__(self, tab: tabs.FileTab):
        super().__init__(tab.bottom_frame)
        self._tab = tab

        self._top_frame = ttk.Frame(self)
        self._top_frame.pack(fill="x")

        # packing order chosen so that if the path is long, everything else
        # disappears before path truncates
        self.path_label = ttk.Label(self._top_frame)
        self.path_label.pack(side="left")
        self._line_ending_button = ttk.Button(
            self._top_frame, command=self._choose_line_ending, style="Statusbar.TButton", width=4
        )
        self._line_ending_button.pack(side="right", padx=2)
        self._encoding_button = ttk.Button(
            self._top_frame, command=self._choose_encoding, style="Statusbar.TButton", width=6
        )
        self._encoding_button.pack(side="right", padx=2)

        self.selection_label = ttk.Label(
            self, text="Non-ASCII character: U+D6 LATIN CAPITAL LETTER O WITH DIAERESIS"
        )
        self.selection_label.pack(side="left")

    def update_labels(self, junk: object = None) -> None:
        if not self.path_label["foreground"]:  # reload warning not going on
            self.path_label.config(text=str(self._tab.path or "File not saved yet"))

        try:
            # For line count, if the cursor is in beginning of line, don't count that as another line.
            chars = count(self._tab.textwidget, "sel.first", "sel.last")
            lines = count(self._tab.textwidget, "sel.first", "sel.last - 1 char", option="-lines")
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
            elif lines == 0:
                text = f"{chars} characters selected"
            else:
                text = f"{chars} characters on {lines+1} lines selected"
            self.selection_label.config(text=text)

        self._encoding_button.config(text=self._tab.settings.get("encoding", str))
        self._line_ending_button.config(
            text=self._tab.settings.get("line_ending", settings.LineEnding).name
        )

    def show_reload_warning(self, event: utils.EventWithData) -> None:
        if event.data_class(tabs.ReloadInfo).had_unsaved_changes:
            oops = utils.get_binding("<<Undo>>")
            text = f"File was reloaded with unsaved changes. Press {oops} to get your changes back."
            self.path_label.config(foreground="red", text=text)

    def clear_reload_warning(self, junk: object) -> None:
        if self.path_label["foreground"]:
            self.path_label.config(foreground="")
            self.update_labels()

    def _choose_encoding(self) -> None:
        new_encoding = utils.ask_encoding(
            "Choose the encoding:", self._tab.settings.get("encoding", str)
        )
        if new_encoding is not None:
            self._tab.settings.set("encoding", new_encoding)
            self.update_labels()

    def _choose_line_ending(self) -> None:
        old_value = self._tab.settings.get("line_ending", settings.LineEnding)
        self._tab.settings.set("line_ending", ask_line_ending(old_value))


def on_new_filetab(tab: tabs.FileTab) -> None:
    statusbar = StatusBar(tab)
    statusbar.pack(side="bottom", fill="x")

    utils.bind_with_data(tab, "<<Reloaded>>", statusbar.show_reload_warning, add=True)
    tab.bind("<<AfterSave>>", statusbar.clear_reload_warning, add=True)

    tab.bind("<<PathChanged>>", statusbar.update_labels, add=True)
    tab.bind("<<TabSettingChanged:encoding>>", statusbar.update_labels, add=True)
    tab.bind("<<TabSettingChanged:line_ending>>", statusbar.update_labels, add=True)
    tab.textwidget.bind("<<CursorMoved>>", statusbar.update_labels, add=True)
    tab.textwidget.bind("<<Selection>>", statusbar.update_labels, add=True)
    statusbar.update_labels()


def update_button_style(junk_event: object = None) -> None:
    # https://tkdocs.com/tutorial/styles.html
    # tkinter's style stuff sucks
    get_tab_manager().tk.eval("ttk::style configure Statusbar.TButton -padding 0 -anchor center")


def setup() -> None:
    get_tab_manager().add_filetab_callback(on_new_filetab)

    get_tab_manager().bind("<<ThemeChanged>>", update_button_style, add=True)
    update_button_style()
