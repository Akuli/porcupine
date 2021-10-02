from __future__ import annotations

import sys
import tkinter
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Callable

from porcupine import get_main_window, utils

from . import history


@dataclass
class CommandSpec:
    command_format: str
    command: str
    cwd_format: str
    cwd: Path
    external_terminal: bool


class FormattingEntryAndLabels:
    def __init__(
        self,
        entry_area: ttk.Frame,
        text: str,
        substitutions: dict[str, str],
        value_validator: Callable[[str], bool],
        validated_callback: Callable[[], None],
    ):
        grid_y = entry_area.grid_size()[1]
        ttk.Label(entry_area, text=text).grid(row=grid_y, column=0, sticky="w")

        self.format_var = tkinter.StringVar()
        self.entry = ttk.Entry(entry_area, font="TkFixedFont", textvariable=self.format_var)
        self.entry.grid(row=grid_y, column=1, sticky="we")
        self.entry.selection_range(0, "end")

        grid_y += 1
        self.label = ttk.Label(entry_area)
        self.label.grid(row=grid_y, column=1, sticky="we")

        # spacer
        grid_y += 1
        ttk.Label(entry_area).grid(row=grid_y)

        self._substitutions = substitutions
        self._value_validator = value_validator
        self._validated_callback = validated_callback
        self.format_var.trace_add("write", self._validate)
        self.value: str | None = None
        self._validate()

    def _validate(self, *junk_from_var_trace: object) -> None:
        try:
            value = self.format_var.get().format(**self._substitutions)
        except (ValueError, KeyError, IndexError):
            self.value = None
            self.label.config(text="Substitution error", font="")
        else:
            self.label.config(text=value, font="TkFixedFont")
            if self._value_validator(value):
                self.value = value
            else:
                self.value = None

        # _validated_callback might not work if called from __init__
        if junk_from_var_trace:
            self._validated_callback()


class CommandAsker:
    def __init__(self, path: Path):
        self.window = tkinter.Toplevel()
        self._suggestions = history.get()

        if sys.platform == "win32":
            terminal_name = "command prompt"
        else:
            terminal_name = "terminal"

        content_frame = ttk.Frame(self.window, borderwidth=10)
        content_frame.pack(fill="both", expand=True)

        project_path = utils.find_project_root(path)
        unquoted_substitutions = {
            "file_stem": path.stem,
            "file_name": path.name,
            "file_path": str(path),
            "folder_name": path.parent.name,
            "folder_path": str(path.parent),
            "project_name": project_path.name,
            "project_path": str(project_path),
        }
        quoted_substitutions = {
            name: utils.quote(value) for name, value in unquoted_substitutions.items()
        }

        entry_area = ttk.Frame(content_frame)
        entry_area.pack(fill="x")
        entry_area.grid_columnconfigure(1, weight=1)

        self.command = FormattingEntryAndLabels(
            entry_area,
            text="Run this command:",
            substitutions=quoted_substitutions,
            value_validator=(lambda command: bool(command.strip())),
            validated_callback=self.update_run_button,
        )
        self.cwd = FormattingEntryAndLabels(
            entry_area,
            text="In this directory:",
            substitutions=unquoted_substitutions,
            value_validator=(lambda d: Path(d).is_dir()),
            validated_callback=self.update_run_button,
        )

        sub_text = "\n".join("{%s} = %s" % pair for pair in unquoted_substitutions.items())
        ttk.Label(content_frame, text=f"Substitutions:\n{sub_text}\n").pack(fill="x")

        # TODO: remember value with settings
        self.terminal_var = tkinter.BooleanVar()

        porcupine_text = (
            "Display the output inside the Porcupine window (does not support keyboard input)"
        )
        external_text = f"Use an external {terminal_name} window"

        ttk.Radiobutton(
            content_frame,
            variable=self.terminal_var,
            value=False,
            text=porcupine_text,
            underline=porcupine_text.index("Porcupine"),
        ).pack(fill="x")
        ttk.Radiobutton(
            content_frame,
            variable=self.terminal_var,
            value=True,
            text=external_text,
            underline=external_text.index("external"),
        ).pack(fill="x")
        self.window.bind("<Alt-p>", (lambda e: self.terminal_var.set(False)), add=True)
        self.window.bind("<Alt-e>", (lambda e: self.terminal_var.set(True)), add=True)

        ttk.Label(content_frame).pack()  # spacer

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill="x")
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.window.destroy)
        cancel_button.pack(side="left", fill="x", expand=True)
        self.run_button = ttk.Button(button_frame, text="Run", command=self.on_run_clicked)
        self.run_button.pack(side="left", fill="x", expand=True)
        self.run_clicked = False

        for entry in [self.command.entry, self.cwd.entry]:
            entry.bind("<Return>", (lambda e: self.run_button.invoke()), add=True)
            entry.bind("<Escape>", (lambda e: self.window.destroy()), add=True)

        if self._suggestions:
            self.command.entry.bind('<Key>', self._autocomplete, add=True)
            self._select_command_autocompletion(self._suggestions[0], prefix="")

        self.command.entry.selection_range(0, "end")
        self.command.entry.focus_set()

    def _select_command_autocompletion(self, item: history.HistoryItem, prefix: str) -> None:
        assert item["command_format"].startswith(prefix)
        self.command.format_var.set(item["command_format"])
        self.command.entry.icursor(len(prefix))
        self.command.entry.selection_range("insert", "end")
        self.cwd.format_var.set(item["cwd_format"])
        self.terminal_var.set(item["external_terminal"])
        return "break"

    def _autocomplete(self, event: tkinter.Event[tkinter.Entry]) -> str | None:
        if len(event.char) != 1:
            return None

        text_to_keep = self.command.entry.get()
        if self.command.entry.selection_present():
            if self.command.entry.index('sel.last') != self.command.entry.index('end'):
                return None
            text_to_keep = text_to_keep[:self.command.entry.index("sel.first")]

        for item in self._suggestions:
            if item["command_format"].startswith(text_to_keep + event.char):
                self._select_command_autocompletion(item, text_to_keep + event.char)
                return "break"

        return None

    def update_run_button(self) -> None:
        if self.command.value is not None and self.cwd.value is not None:
            self.run_button.config(state="normal")
        else:
            self.run_button.config(state="disabled")

    def on_run_clicked(self) -> None:
        self.run_clicked = True
        self.window.destroy()


def ask_command(path: Path) -> CommandSpec | None:
    asker = CommandAsker(path)
    asker.window.title("Run command")
    asker.window.transient(get_main_window())
    asker.window.wait_window()

    if asker.run_clicked:
        assert asker.command.value is not None
        assert asker.cwd.value is not None
        return CommandSpec(
            command_format=asker.command.format_var.get(),
            command=asker.command.value,
            cwd_format=asker.cwd.format_var.get(),
            cwd=Path(asker.cwd.value),
            external_terminal=asker.terminal_var.get(),
        )
    return None
